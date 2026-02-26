# PaaSBuilder

The `PaaSBuilder` is a builder that is focused on PaaS entities management. The main purpose of this builder is to provide a simple way to manage PaaS entities resources. The builder inherits from `UniversalBuilder` so you can override any method of the builder to provide custom logic. The builder extends the interface of the `UniversalBuilder` with some specific methods.

Also the builder has a set of methods allowing to schedule PaaS objects to particular agents based on the agent capabilities.

## create_paas_objects

Create a list of PaaS objects. The method returns a list of PaaS objects that are required for the instance.

You don't need to implement the method `create_instance_derivatives` as `PaaSBuilder` implements it and uses the `create_paas_objects` method to create derivatives.

## actualize_paas_objects_source_data_plane

Actualize the PaaS objects. Changes from the data plane. The method is called when the instance is outdated. For example, the instance `Database` has derivative `PGDatabase`. Single `Database` may have multiple `PGDatabase` derivatives. If any of the derivatives is outdated, this method is called to reactualize these PaaS objects.

This method replaces the `actualize_outdated_instance_derivatives` method of the `UniversalBuilder`.

## enable_schedule_paas_objects

Enable schedule PaaS objects.

## actualize_paas_objects_source_master

Actualize the PaaS objects. Changes from the master instance. The method is called when the instance is outdated from master instance point of view. For example, the instance `Database` is linked to the `NodeSet` instance. If the `NodeSet` is outdated, this method is called to reactualize the `Database` instance.


## schedule_paas_objects

Schedule the PaaS objects. The method schedules the PaaS objects. The result is a dictionary where the key is a UUID of an agent and the value is a list of PaaS objects that should be scheduled on this agent. If you don't want to schedule the PaaS objects, skip implementation of this method.