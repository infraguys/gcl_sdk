# Universal Builder

The Universal Builder is a service that provides some common logic to build resources and prepare them for agents based on the universal agent.
Every builder works with a particular instance model. The instance is a key element of the builder and it sets in the builder constructor. The instance represents a real object of the control plane we want to build. For example, `Config`, `Secret`, `PGInstance` and so on.

The key feature of the universal builder is to do all routine work for service lifecycle management, preparing and converting instances to universal agent resources, tracking and actualizing their states. The universal builder has an interface as a set of methods that may be overridden to provide custom logic but most of them have default implementation.

## Quick start

Follow the [quick start guide](universal_builder_quick_start) to run the Universal Builder.

## Main terms

### Instance

As described above the instance is a real object of the control plane but to work with the universal builder such instances should inherit from `InstanceMixin` or `InstanceWithDerivativesMixin`. They are useful mixins that allow to translate the real object (from the control plane) to the universal agent resources.

### InstanceMixin

This is a core mixin for models that is going to be used in builder.

Any models that is going to be used in universal builders should inherit from this mixin since it provides the necessary methods to work with the universal builder. Two main group of methods are provided:

- methods to fetch entities from the database.
- methods to work with derivatives.

The derivatives objects are the objects that are created from the instance object and strongly coupled with it. For example, the config instance has derivatives like render objects. Single config instance can have multiple render objects.

The default behavior for the `InstanceMixin` is to not have derivatives.

### InstanceWithDerivativesMixin

Another core mixin for models that is going to be used in builder.

See `InstanceMixin` for core functionality. The key difference is that this mixin is focusing on instances that have derivatives.

The default behavior is to have derivatives objects.

## Universal Builder interface

The universal builder interface is a set of methods that may be overridden to provide custom logic but most of them have default implementation.

### pre_create_instance_resource

The hook is performed before creating instance resource. The hook is called only for new instances.

### create_instance_derivatives

Create the instance. The result is a collection of derivative objects that are required for the instance. For example, the main instance is a `Config` so the derivative objects for the config is a list of `Render`. The result is a collection of render objects. The derivative objects should inherit from the `TargetResourceMixin`.

### post_create_instance_resource

The hook is performed after saving instance resource. The hook is called only for new instances.

### pre_update_instance_resource

The hook is performed before updating instance resource.

### update_instance_derivatives

The hook to update instance derivatives. The hook is called when an initiator of updating is a user. The default implementation is to delete the outdated derivatives and create new ones.

NOTE: The default implementation of the method may be dangerous in cases if the derivatives are changed in live cycle of the instance. For instance, if new derivatives are added after the instance was created, they will be dropped in the default implementation of the method.

### post_update_instance_resource

The hook is performed after updating instance resource.

### actualize_outdated_instance

Actualize outdated instance. It means some changes occurred on the data plane and the instance is outdated now. For example, the instance `Password` has field `value` that is stored in the secret storage. If the value is changed or created on the data plane, the instance is outdated and this method is called to reactualize the instance.

### actualize_outdated_instance_derivatives

Actualize outdated instance with derivatives. It means some changes occurred on the data plane and the instance is outdated now. For example, the instance `Config` has derivative `Render`. Single `Config` may have multiple `Render` derivatives. If any of the derivatives is outdated, this method is called to reactualize the derivatives. The method returns the list of `updated` derivatives. If nothing needs to be updated, the method returns the same list of target derivatives as it received. Otherwise, the method should return the list of updated derivatives. It also can add new or remove old derivatives.

Depends on the `fetch_all_derivatives_on_outdate` the behavior of the method is different:

**fetch_all_derivatives_on_outdate == True:**
The method receives the list of all derivatives currently available for the instance even though the derivatives aren't outdated.

**fetch_all_derivatives_on_outdate == False:**
The method receives the list only changed derivatives from the last actualization. For example, a config has two renders. Only one of them is outdated. The method receives the list of only one outdated render.

### pre_delete_instance_resource

The hook is performed before deleting instance resource.

### track_outdated_master_hash_instances

Track outdated master instances. It's called if the hash of the master instance isn't equal to the saved master hash.

### track_outdated_master_full_hash_instances

Track outdated master instances. It's called if the full hash of the master instance isn't equal to the saved master full hash.

### actualize_outdated_master_hash_instance

Actualize instance if the hash of the master instance isn't equal to the saved master hash. The logic is quite similar to `actualize_outdated_instance_derivatives`.
But the reason when this method is called is different. The `actualize_outdated_instance_derivatives` allows to track changes on the data plane but this method allows to track changes on a related master instance. For example, the instance model is `Database`, the related master for this instance is `NodeSet`. If the `NodeSet` is updated, this method is called for all `Database` instances that are related to this `NodeSet` to reactualize them. This method tracks changes for target fields of the master instance.

### actualize_outdated_master_full_hash_instance

Actualize instance if the full hash of the master instance isn't equal to the saved master full hash. The logic is quite similar to `actualize_outdated_instance_derivatives`.
But the reason when this method is called is different. The `actualize_outdated_instance_derivatives` allows to track changes on the data plane but this method allows to track changes on a related master instance. For example, the instance model is `Database`, the related master for this instance is `NodeSet`. If the `NodeSet` is updated, this method is called for all `Database` instances that are related to this `NodeSet` to reactualize them. This method tracks changes for all fields of the master instance.

## Specific builders

There is a set of specific builders that are already implemented in the SDK and they are focused on particular aspects.

### CoreInfraBuilder

The `CoreInfraBuilder` is a builder that is focused on infrastructure management. See the [CoreInfraBuilder](core_infra_builder) for more details.

### PaaSBuilder

The `PaaSBuilder` is a builder that is focused on management of PaaS entities. See the [PaaSBuilder](paas_builder) for more details.
