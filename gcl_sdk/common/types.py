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

import typing as tp

from restalchemy.dm import types


class SchematicType(types.SoftSchemeDict):
    """A type that validates a dictionary against a schema.

    The schema is defined in the `__scheme__` attribute.
    The mandatory fields are defined in the `__mandatory__` attribute.

    The mandatory fields are checked before the schema validation.
    If the mandatory fields are not present in the dictionary,
    the validation fails.

    Example:
    >>> class MyType(SchematicType):
    >>>     __scheme__ = {
    >>>         "a": types.Integer(),
    >>>         "b": types.Integer(),
    >>>     }
    >>>     __mandatory__ = {"a"}
    >>>
    >>> MyType({"a": 1, "b": 2}).validate()
    True
    >>> MyType({"b": 2}).validate()
    False
    """

    __scheme__ = {}
    __mandatory__ = set()

    def __init__(self):
        if len(self.__mandatory__) > 0 and not self.__mandatory__.issubset(
            self.__scheme__.keys()
        ):
            raise ValueError(
                "Mandatory fields have to be defined in the schema"
            )

        super().__init__(self.__scheme__)

    def validate(self, value: dict[str, tp.Any]) -> bool:
        if len(self.__mandatory__) == 0:
            return super().validate(value)

        return set(value.keys()).issuperset(
            self.__mandatory__
        ) and super().validate(value)
