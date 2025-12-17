#    Copyright 2025 Genesis Corporation.
#
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from __future__ import annotations

import os
import logging
import shutil
import subprocess

from gcl_sdk.agents.universal.drivers import exceptions as driver_exc
from gcl_sdk.agents.universal.drivers import meta
from gcl_sdk.agents.universal import constants
from gcl_sdk.infra import constants as ic
from gcl_sdk.paas.dm import lb as lb_models


LOG = logging.getLogger(__name__)

LB_TARGET_KIND = "paas_lb_node"
BALANCE_MAPPING = {
    "roundrobin": "",
    "leastconn": "least_conn;",
}
NGINX_L7_CONFIG_FILE = "/etc/nginx/conf.d/genesis_lb.conf"
NGINX_L4_CONFIG_FILE = "/etc/nginx/genesis/l4.conf"
NGINX_SSL_DIR = "/etc/nginx/ssl/"
NGINX_USER = NGINX_GROUP = "www-data"
# Drop all if not set by user, convenient default
ROOT_LOCATION = """\
location / {
        return 444;
    }
"""
LOCATION_TYPE_MAPPING = {
    "prefix": "",
    "exact": "=",
    "regex": "~",
}
ADD_HEADERS_MAPPING = {
    "Host": "proxy_set_header Host $host;",
    "X-Forwarded-For": "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
    "X-Forwarded-Proto": "proxy_set_header X-Forwarded-Proto $scheme;",
    "X-Forwarded-Port": (
        lambda vhost, route: (
            f'proxy_set_header X-Forwarded-Port "{vhost['port']}";'
        )
    ),
    "X-Forwarded-Prefix": (
        lambda vhost, route: (
            f'proxy_set_header X-Forwarded-Prefix "{route['value']}";'
            if route["value"] != "/"
            else ""
        )
    ),
}


def secure_opener(path, flags):
    return os.open(path, flags, 0o700)


class LB(lb_models.LB, meta.MetaDataPlaneModel):

    def get_meta_model_fields(self) -> set[str] | None:
        """Return a list of meta fields or None.

        Meta fields are the fields that cannot be fetched from
        the data plane or we just want to save them into the meta file.

        `None` means all fields are meta fields but it doesn't mean they
        won't be updated from the data plane.
        """

        # Keep all fields as meta fields for simplicity
        return {
            "uuid",
            "vhosts",
            "backend_pools",
        }

    def _gen_backends(self, proto_lvl):
        upstreams = []
        for pid, pool in self.backend_pools.items():
            upstreams.append(
                f"""\
upstream {pid} {{
    {BALANCE_MAPPING[pool.get('balance', 'roundrobin')]}
    zone {pid}_{proto_lvl} 64K;
    {'\n    '.join(f"    server {e['host']}:{e['port']} weight={e['weight']};" for e in pool['endpoints'] if e['kind'] == 'host')}
    {'keepalive 2;' if proto_lvl == 'l7' else ''}
}}
"""
            )
        return upstreams

    def _gen_modifiers(self, vhost, route, modifiers):
        res = []
        for m in modifiers:
            if m["kind"] == "auto_header":
                for h in m["headers"]:
                    val = ADD_HEADERS_MAPPING[h]
                    res.append(val(vhost, route) if callable(val) else val)
            elif m["kind"] == "set_header":
                res.append(
                    f'proxy_set_header "{m['name'].replace('"', '\\"')}" "{m['value'].replace('"', '\\"')}";'
                )
            elif m["kind"] == "rewrite_url":
                res.append(
                    f'rewrite "{m['regex'].replace('"', '\\"')}" "{m['replacement'].replace('"', '\\"')}" break;'
                )
        return res

    def _gen_vhosts(self):
        vhosts_l4 = []
        vhosts_l7 = []
        for v in self.vhosts:
            if len(v["routes"]) == 0:
                continue
            if v["proto"].startswith("http"):
                vhosts_l7.append(self._gen_vhost_l7(v))
            else:
                vhosts_l4.append(self._gen_vhost_l4(v))
        return vhosts_l4, vhosts_l7

    def _gen_vhost_l4(self, v):
        for r in v["routes"].values():
            c = r["cond"]
            return f"""\
server {{
listen 0.0.0.0:{v['port']}{f" {v['proto']}" if v['proto'] != 'tcp' else ""};
{('    \n').join(f"allow {ip};" for ip in c['allowed_ips'])}
deny all;
proxy_pass {c["actions"][0]["pool"]};
}}
"""
        return ""

    def _gen_file_content_l4(self, vhosts) -> str:
        return f"""\
stream {{
{"\n".join(b for b in self._gen_backends(proto_lvl="l4"))}

{"\n".join(v for v in vhosts)}
}}
"""

    def _gen_vhost_l7(self, v):
        locations = [ROOT_LOCATION]
        for r in v["routes"].values():
            c = r["cond"]

            actions = []
            for a in c["actions"]:
                if a["kind"] == "backend":
                    actions.append(
                        f"""\
proxy_pass {a["protocol"]["kind"]}://{a["pool"]};"""
                    )
                    if (
                        a["protocol"]["kind"] == "https"
                        and a["protocol"]["verify"] is not True
                    ):
                        actions.append("proxy_ssl_verify off;")
                    break
                elif a["kind"] == "redirect":
                    actions.append(
                        f"""\
return {a["code"]} {a["url"]}$request_uri;"""
                    )
                    break
                elif a["kind"] == "local_dir":
                    actions.append(
                        f"""\
alias {os.path.join(a['path'], '')};"""
                    )
                    break
            # Upgrade + Connection headers must be inside location
            loc = f"""
location {LOCATION_TYPE_MAPPING[c['kind']]} {c['value']} {{
    {"\n    ".join(a for a in actions)}
    {"\n    ".join(m for m in self._gen_modifiers(v, c, c['modifiers']))}
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
}}"""
            if c["value"] == "/":
                # Replace default root location
                locations[0] = loc
            else:
                locations.append(loc)

        if v["proto"] == "https":
            ssl_info = f"""
ssl_certificate      {NGINX_SSL_DIR}{v['uuid']}.crt;
ssl_certificate_key  {NGINX_SSL_DIR}{v['uuid']}.key;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ecdh_curve X25519:prime256v1:secp384r1;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384:DHE-RSA-CHACHA20-POLY1305;
"""
        else:
            ssl_info = ""
        return f"""\
server {{
listen 0.0.0.0:{v['port']}{' ssl http2' if v['proto'] == 'https' else ''};
server_name {' '.join(v['domains'])};{ssl_info}
{('    \n').join(f"allow {ip};" for ip in c['allowed_ips'])}
deny all;
{"\n    ".join(locations)}
}}
"""

    def _gen_http_defaults(self) -> str:
        return """\
ssl_session_timeout 10m;
ssl_session_cache shared:SSL:10m;
gzip_proxied any;
client_max_body_size 0;
server_tokens off;

map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

"""

    def _gen_file_content_l7(self, vhosts) -> str:
        return f"""\
{self._gen_http_defaults()}

{"\n".join(b for b in self._gen_backends(proto_lvl="l7"))}

{"\n".join(v for v in vhosts)}
"""

    def _reload_or_restart_nginx(self):
        try:
            subprocess.check_call(["systemctl", "reload", "nginx"])
        except subprocess.CalledProcessError:
            subprocess.check_call(["systemctl", "restart", "nginx"])

    def dump_to_dp(self) -> None:
        vhosts_l4, vhosts_l7 = self._gen_vhosts()
        with open(NGINX_L4_CONFIG_FILE, "w") as f:
            f.write(self._gen_file_content_l4(vhosts_l4))

        with open(NGINX_L7_CONFIG_FILE, "w") as f:
            f.write(self._gen_file_content_l7(vhosts_l7))

        for v in self.vhosts:
            if v["proto"] != "https":
                continue
            crt_name = f"{NGINX_SSL_DIR}{v['uuid']}.crt"
            with open(crt_name, "w", opener=secure_opener) as f:
                f.write(v["cert"]["crt"])
            shutil.chown(crt_name, user=NGINX_USER, group=NGINX_GROUP)
            key_name = f"{NGINX_SSL_DIR}{v['uuid']}.key"
            with open(key_name, "w", opener=secure_opener) as f:
                f.write(v["cert"]["key"])
            shutil.chown(key_name, user=NGINX_USER, group=NGINX_GROUP)

        self._reload_or_restart_nginx()
        self.status = ic.InstanceStatus.ACTIVE.value

    def _validate_file(self, path, expected_content):
        try:
            with open(path, "r") as f:
                if expected_content != f.read():
                    raise driver_exc.InvalidDataPlaneObjectError(
                        obj={"uuid": str(self.uuid)}
                    )
        except FileNotFoundError:
            raise driver_exc.InvalidDataPlaneObjectError(
                obj={"uuid": str(self.uuid)}
            )

    def restore_from_dp(self) -> None:
        try:
            subprocess.check_output(["systemctl", "is-active", "nginx"])
            self.status = ic.InstanceStatus.ACTIVE.value
        except subprocess.CalledProcessError:
            raise driver_exc.InvalidDataPlaneObjectError(
                obj={"uuid": str(self.uuid)}
            )

        vhosts_l4, vhosts_l7 = self._gen_vhosts()
        # Force file validation
        self._validate_file(
            NGINX_L4_CONFIG_FILE, self._gen_file_content_l4(vhosts_l4)
        )
        self._validate_file(
            NGINX_L7_CONFIG_FILE, self._gen_file_content_l7(vhosts_l7)
        )
        for v in self.vhosts:
            if v["proto"] == "https":
                self._validate_file(
                    f"{NGINX_SSL_DIR}{v['uuid']}.crt", v["cert"]["crt"]
                )
                self._validate_file(
                    f"{NGINX_SSL_DIR}{v['uuid']}.key", v["cert"]["key"]
                )

    def _remove_file(self, path):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    def delete_from_dp(self) -> None:
        self._remove_file(NGINX_L4_CONFIG_FILE)
        self._remove_file(NGINX_L7_CONFIG_FILE)

        for v in self.vhosts:
            if v["proto"] == "https":
                self._remove_file(f"{NGINX_SSL_DIR}{v['uuid']}.crt")
                self._remove_file(f"{NGINX_SSL_DIR}{v['uuid']}.key")

        self._reload_or_restart_nginx()

    def update_on_dp(self) -> None:
        self.dump_to_dp()


class LBCapabilityDriver(meta.MetaFileStorageAgentDriver):
    META_PATH = os.path.join(constants.WORK_DIR, "lb_meta.json")

    __model_map__ = {LB_TARGET_KIND: LB}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, meta_file=self.META_PATH, **kwargs)
