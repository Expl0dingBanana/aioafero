Feature identity
================

Every feature model owns the Afero identity used for outbound states:
``function_class`` and ``function_instance``. Both arguments are required and
keyword-only. Pass ``None`` explicitly when the API state has no instance.

For example:

.. code-block:: python

   from aioafero.v1.models.features import OnFeature

   fan_power = OnFeature(
       on=True,
       function_class="power",
       function_instance="fan-power",
   )
   outlet_power = OnFeature(
       on=False,
       function_class="power",
       function_instance=None,
   )

Controllers populate this metadata from incoming Afero states and preserve it
when building updates. Code that only reads features returned by controllers
does not need to supply the fields itself.

Migrating to 8.0
----------------

Feature construction is intentionally incompatible with 7.x:

* Rename ``func_class`` to ``function_class``.
* Rename ``func_instance`` and ``TargetTemperatureFeature.instance`` to
  ``function_instance``.
* Rename ``get_afero_state_from_feature()`` keyword parameters to
  ``function_class``, ``function_instance``, and ``current_value``.
* Supply both identity arguments explicitly; there are no compatibility
  aliases or defaults.
* Treat ``api_value`` as the value only. It no longer returns a complete Afero
  state envelope.

The serializer combines a feature's identity and value centrally. Custom
feature implementations should inherit ``AferoFeature`` and implement
``api_value``. Override ``iter_afero_values()`` only when one feature must emit
multiple ordered Afero states, such as a custom color-sequence effect.

``EffectFeature`` is the built-in plural-emission case. Its owned
``function_class`` is used for every emitted state, while the emitted
``functionInstance`` values are derived from the selected effect group
(``preset``, ``custom``, and similar). Its stored ``function_instance`` identifies
the canonical inbound row; it is not a list of all instances emitted by a PUT.
