# Universal Builder

The Universal Builder is a service that provides some common logic to build resources and prepare them for agents based on the universal agent.
Every builder works with a particular instance model. The instance is a key element of the builder and it sets in the builder constructor. The instance represents a real object of the control plane we want to build. For example, `Config`, `Secret`, `PGInstance` and so on.

The key feature of the universal builder is to do all routine work for service lifecycle management, preparing and converting instances to universal agent resources, tracking and actualizing their states. The universal builder has an interface as a set of methods that may be overridden to provide custom logic but most of them have default implementation.

## Quick start

Follow the [quick start guide](universal_builder_quick_start.md) to run the Universal Builder.

## Main terms

### Instance

As described above the instance is a real object of the control plane but to work with the universal builder such instances should inherit from `InstanceMixin` or `InstanceWithDerivativesMixin`. They are useful mixins that allow to translate a real object (from the control plane) to universal agent resources.

### InstanceMixin

This is a core mixin for models that is going to be used in builder.

Any models that is going to be used in universal builders should inherit from this mixin since it provides the necessary methods to work with the universal builder. Three main group of methods are provided:

- methods to fetch entities from the database.
- methods to work with derivatives.
- methods to work with tracked resources

The derivatives objects are the objects that are created from the instance object and strongly coupled with it. For example, the config instance has derivatives like render objects. Single config instance can have multiple render objects.

The default behavior for the `InstanceMixin` is to not have derivatives.

Tracked resources are the resources that are tracked by the instance. For example, the config instance tracks the node resource to ensure that the node is alive.

### InstanceWithDerivativesMixin

Another core mixin for models that is going to be used in builder.

See `InstanceMixin` for core functionality. The key difference is that this mixin is focusing on instances that have derivatives.

The default behavior is to have derivatives objects.

## Universal Builder interface

The Universal Builder inherits from `RegistrableUAServiceMixin` which is a helper mixin for services that work with Universal Builder and Universal Agent.

For the Universal Builder, this mixin provides:

- a unified interface for registering a service with the Universal Agent;
- a description of which capabilities and resources the service can handle;

The universal builder interface is a set of methods that may be overridden to provide custom logic but most of them have default implementation.

There are five vectors of the interaction with instances:

| Vector | Description | Initiator |
|--------|-------------|-----------|
| Create | Create an instance. By a user or outer automation. | User/Outer automation |
| Update | Update an instance. By a user or outer automation. | User/Outer automation |
| Delete | Delete an instance. By a user or outer automation. | User/Outer automation |
| Outdate | Derivative objects are changed for some reason. For instance, the derivative object is ready and its status is set to `ACTIVE` | Derivative objects |
| Track | Tracked resources are changed for some reason. For instance, the tracked resource is ready and its status is set to `ACTIVE` | Tracked resources |

Also a master resource that can be outdated by some reason but it's very similar to `derivatives` vector so it's handled in the same way.

```
                                                 User/Outer automation
                                                         |
                                                         | **Create vector**
                                                         | can_create_instance_resource
                                                         | pre_create_instance_resource
                                                         | create_instance_derivatives
                                                         | post_create_instance_resource
                                                         v
        Tracked resources                              +---------------------------+     User/Outer automation
        |                                              |     UniversalBuilder      |       |
        |                                              |                           |       |
        |                                              |   +-------------------+   |       |
        | **Track vector**                             |   |                   |   |       | **Update vector**
        | get_tracked_instances_on_create              |   |    Instance       |   |       | can_update_instance_resource
        | get_tracked_instances_on_update              |   |                   |   |       | pre_update_instance_resource
        | track_outdated_master_hash_instances         |   |                   |   |       | update_instance_derivatives
        | track_outdated_master_full_hash_instances    |   |                   |   |       | post_update_instance_resource
        |                                              |   |                   |   | <-----+
        +------------------------------------------>   |   |                   |   |
                                                       |   |                   |   |
        Derivative resources                           |   +-------------------+   |
        |                                              |                           |
        | **Outdate vector**                           |                           |
        | can_actualize_outdated_instance_resource     |                           |
        | actualize_outdated_instance                  |                           |
        | actualize_outdated_instance_derivatives      |                           |
        | actualize_outdated_master_hash_instance      |                           |
        | actualize_outdated_master_full_hash_instance |                           |
        |                                              |                           |
        +------------------------------------------>   |                           |
                                                       +---------------------------+
                                                          ^
                                                          |
                                                          | **Delete vector**
                                                          | can_delete_instance_resource
                                                          | pre_delete_instance_resource
                                                          |
                                                 User/Outer automation
```

### Common

#### ua_service_spec

The service specification for the universal builder service. It can be used to define the capabilities of the service in `UAServiceSpec` format.

#### prepare_iteration

The hook to prepare the iteration. The hook is called before the iteration and should return the iteration context. The iteration context is a dictionary. The context is available in the iteration methods as `self._iteration_context`.

### Create vector

Hooks related to the create vector.

#### can_create_instance_resource

The hook to check if the instance can be created.

If the hook returns `False`, the code related to the instance:
- `pre_create_instance_resource`
- `create_instance_derivatives`
- `post_create_instance_resource`
will be skipped for the current iteration. The
`can_create_instance_resource` will be called again on the next
iteration until it returns `True`.

#### pre_create_instance_resource

The hook is performed before creating instance resource. The hook is called only for new instances.

#### create_instance_derivatives

Create the instance. The result is a collection of derivative objects that are required for the instance. For example, the main instance is a `Config` so the derivative objects for the config is a list of `Render`. The result is a collection of render objects. The derivative objects should inherit from the `TargetResourceMixin`.

#### post_create_instance_resource

The hook is performed after saving instance resource. The hook is called only for new instances.

### Update vector

Hooks related to the update vector.

#### can_update_instance_resource

The hook to check if the instance can be updated.

If the hook returns `False`, the code related to the instance:
- `pre_update_instance_resource`
- `update_instance_derivatives`
- `post_update_instance_resource`
will be skipped for the current iteration. The
`can_update_instance_resource` will be called again on the next
iteration until it returns `True`.

#### pre_update_instance_resource

The hook is performed before updating instance resource.

#### update_instance_derivatives

The hook to update instance derivatives. The hook is called when an initiator of updating is a user or outer automation. The default implementation is **to delete the outdated derivatives and create new ones**.

NOTE: The default implementation of the method may be dangerous in cases if the derivatives are changed in live cycle of the instance. For instance, if new derivatives are added after the instance was created, they will be dropped in the default implementation of the method.

#### post_update_instance_resource

The hook is performed after updating instance resource.

### Outdate vector

The outdate vector is used to actualize instances that are outdated. It means some changes occurred on the data plane and the instance is outdated now.

#### can_actualize_outdated_instance_resource

The hook to check if the instance can be actualized.

If the hook returns `False`, the code related to the instance:
- `actualize_outdated_instance`
- `actualize_outdated_instance_derivatives`
will be skipped for the current iteration. The
`can_actualize_outdated_instance_resource` will be called again on
the next iteration until it returns `True`.

#### actualize_outdated_instance

Actualize outdated instance. It means some changes occurred on the data plane and the instance is outdated now. For example, the instance `Password` has field `value` that is stored in the secret storage. If the value is changed or created on the data plane, the instance is outdated and this method is called to reactualize the instance.

#### actualize_outdated_instance_derivatives

Actualize outdated instance with derivatives. It means some changes occurred on the data plane and the instance is outdated now. For example, the instance `Config` has derivative `Render`. Single `Config` may have multiple `Render` derivatives. If any of the derivatives is outdated, this method is called to reactualize the derivatives. The method returns the list of `updated` derivatives. If nothing needs to be updated, the method returns the same list of target derivatives as it received. Otherwise, the method should return the list of updated derivatives. It also can add new or remove old derivatives.

Depends on the `fetch_all_derivatives_on_outdate` the behavior of the method is different:

**fetch_all_derivatives_on_outdate == True:**
The method receives the list of all derivatives currently available for the instance even though the derivatives aren't outdated.

**fetch_all_derivatives_on_outdate == False:**
The method receives the list only changed derivatives from the last actualization. For example, a config has two renders. Only one of them is outdated. The method receives the list of only one outdated render.

#### actualize_outdated_master_hash_instance

Actualize instance if the hash of the master instance isn't equal to the saved master hash. The logic is quite similar to `actualize_outdated_instance_derivatives`.
But the reason when this method is called is different. The `actualize_outdated_instance_derivatives` allows to track changes on the data plane but this method allows to track changes on a related master instance. For example, the instance model is `Database`, the related master for this instance is `NodeSet`. If the `NodeSet` is updated, this method is called for all `Database` instances that are related to this `NodeSet` to reactualize them. This method tracks changes for target fields of the master instance.

#### actualize_outdated_master_full_hash_instance

Actualize instance if the full hash of the master instance isn't equal to the saved master full hash. The logic is quite similar to `actualize_outdated_instance_derivatives`.
But the reason when this method is called is different. The `actualize_outdated_instance_derivatives` allows to track changes on the data plane but this method allows to track changes on a related master instance. For example, the instance model is `Database`, the related master for this instance is `NodeSet`. If the `NodeSet` is updated, this method is called for all `Database` instances that are related to this `NodeSet` to reactualize them. This method tracks changes for all fields of the master instance.

### Delete vector

Hooks to delete instance resources.

#### can_delete_instance_resource

The hook to check if the instance can be deleted.

If the hook returns `False`, the code related to the instance:
- `pre_delete_instance_resource`
will be skipped for the current iteration. The
`can_delete_instance_resource` will be called again on the next
iteration until it returns `True`.

#### pre_delete_instance_resource

The hook is performed before deleting instance resource.

### Track vector

Hooks to track instance resources.

#### get_tracked_instances_on_create

The hook to collect tracked instances on create. The hook is called only for new instances.

#### get_tracked_instances_on_update

The hook to collect tracked instances on update. The hook is called only for updated instances.

#### track_outdated_master_hash_instances

Track outdated master instances. It's called if the hash of the master instance isn't equal to the saved master hash.

#### track_outdated_master_full_hash_instances

Track outdated master instances. It's called if the full hash of the master instance isn't equal to the saved master full hash.

## Scheduling

The scheduling is a process of assigning a resource to an agent. There are several ways to schedule a resource:

- **Universal scheduler** - If resources have simple scheduling logic, for example, they are assigned to the first available agent, you can use the universal scheduler. Please see the [UniversalScheduler](../universal_scheduler/universal_scheduler.md) for more details.
- **SchedulableToAgentMixin** - A helpful mixin an instance can inherit from to schedule itself to an agent. For that it should implement the `schedule_to_ua_agent` method. There are already several implementations of this mixin in the SDK:
    - `SchedulableToAgentFromNodeMixin` - schedules the resource to the UA agent based on the node UUID.
    - `SchedulableToAgentFromAgentUUIDMixin` - schedules the resource to the UA agent based on the agent UUID.
- **Own scheduler service** - If you need to complex logic for scheduling, you can create your own scheduler service.

## Readiness to perform operations

The readiness is a process of checking if an instance is ready to perform an operation such as create, update, delete or actualize. For example, the instance `config` depends on a node, the config cannot be created until the node is created. To implement such readiness logic, you can use the `ReadinessMixin` mixin.

**ReadinessMixin** - A helpful mixin an instance can inherit from to check if it is ready to perform an operation. For that it should implement the `is_ready_to_*` methods. There are already several implementations of this mixin in the SDK:
- `DependenciesExistReadinessMixin` - checks if all dependencies exist.
- `DependenciesActiveReadinessMixin` - checks if all dependencies exist and are active.

## Specific builders

There is a set of specific builders that are already implemented in the SDK and they are focused on particular aspects.

### CollectionUniversalBuilderService

The `CollectionUniversalBuilderService` is a service that is focused on managing a collection of instances. You can pass a list of instance models via `instance_models` parameter.


### CoreInfraBuilder

The `CoreInfraBuilder` is a builder that is focused on infrastructure management. See the [CoreInfraBuilder](core_infra_builder.md) for more details.

### PaaSBuilder

The `PaaSBuilder` is a builder that is focused on management of PaaS entities. See the [PaaSBuilder](paas_builder.md) for more details.
