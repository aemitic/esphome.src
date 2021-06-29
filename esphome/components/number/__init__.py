import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation
from esphome.components import mqtt
from esphome.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_EXPIRE_AFTER,
    CONF_ICON,
    CONF_ID,
    CONF_INTERNAL,
    CONF_ON_VALUE,
    CONF_ON_VALUE_RANGE,
    CONF_TRIGGER_ID,
    CONF_NAME,
    CONF_MQTT_ID,
    ICON_EMPTY,
)
from esphome.core import CORE, coroutine_with_priority

CODEOWNERS = ["@esphome/core"]
IS_PLATFORM_COMPONENT = True

number_ns = cg.esphome_ns.namespace("number")
Number = number_ns.class_("Number", cg.Nameable)
NumberPtr = Number.operator("ptr")

# Triggers
NumberStateTrigger = number_ns.class_(
    "NumberStateTrigger", automation.Trigger.template(cg.float_)
)
ValueRangeTrigger = number_ns.class_(
    "ValueRangeTrigger", automation.Trigger.template(cg.float_), cg.Component
)

# Actions
NumberPublishAction = number_ns.class_("NumberPublishAction", automation.Action)

# Conditions
NumberInRangeCondition = number_ns.class_(
    "NumberInRangeCondition", automation.Condition
)

icon = cv.icon


NUMBER_SCHEMA = cv.MQTT_COMPONENT_SCHEMA.extend(
    {
        cv.OnlyWith(CONF_MQTT_ID, "mqtt"): cv.declare_id(mqtt.MQTTNumberComponent),
        cv.GenerateID(): cv.declare_id(Number),
        cv.Optional(CONF_ICON, default=ICON_EMPTY): icon,
        cv.Optional(CONF_EXPIRE_AFTER): cv.All(
            cv.requires_component("mqtt"),
            cv.Any(None, cv.positive_time_period_milliseconds),
        ),
        cv.Optional(CONF_ON_VALUE): automation.validate_automation(
            {
                cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(NumberStateTrigger),
            }
        ),
        cv.Optional(CONF_ON_VALUE_RANGE): automation.validate_automation(
            {
                cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(ValueRangeTrigger),
                cv.Optional(CONF_ABOVE): cv.float_,
                cv.Optional(CONF_BELOW): cv.float_,
            },
            cv.has_at_least_one_key(CONF_ABOVE, CONF_BELOW),
        ),
    }
)


async def setup_number_core_(var, config):
    cg.add(var.set_name(config[CONF_NAME]))
    if CONF_INTERNAL in config:
        cg.add(var.set_internal(config[CONF_INTERNAL]))

    cg.add(var.set_icon(config[CONF_ICON]))

    for conf in config.get(CONF_ON_VALUE, []):
        trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], var)
        await automation.build_automation(trigger, [(float, "x")], conf)
    for conf in config.get(CONF_ON_VALUE_RANGE, []):
        trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], var)
        await cg.register_component(trigger, conf)
        if CONF_ABOVE in conf:
            template_ = await cg.templatable(conf[CONF_ABOVE], [(float, "x")], float)
            cg.add(trigger.set_min(template_))
        if CONF_BELOW in conf:
            template_ = await cg.templatable(conf[CONF_BELOW], [(float, "x")], float)
            cg.add(trigger.set_max(template_))
        await automation.build_automation(trigger, [(float, "x")], conf)

    if CONF_MQTT_ID in config:
        mqtt_ = cg.new_Pvariable(config[CONF_MQTT_ID], var)
        await mqtt.register_mqtt_component(mqtt_, config)

        if CONF_EXPIRE_AFTER in config:
            if config[CONF_EXPIRE_AFTER] is None:
                cg.add(mqtt_.disable_expire_after())
            else:
                cg.add(mqtt_.set_expire_after(config[CONF_EXPIRE_AFTER]))


async def register_number(var, config):
    if not CORE.has_id(config[CONF_ID]):
        var = cg.Pvariable(config[CONF_ID], var)
    cg.add(cg.App.register_number(var))
    await setup_number_core_(var, config)


async def new_number(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await register_number(var, config)
    return var


NUMBER_IN_RANGE_CONDITION_SCHEMA = cv.All(
    {
        cv.Required(CONF_ID): cv.use_id(Number),
        cv.Optional(CONF_ABOVE): cv.float_,
        cv.Optional(CONF_BELOW): cv.float_,
    },
    cv.has_at_least_one_key(CONF_ABOVE, CONF_BELOW),
)


@automation.register_condition(
    "number.in_range", NumberInRangeCondition, NUMBER_IN_RANGE_CONDITION_SCHEMA
)
async def number_in_range_to_code(config, condition_id, template_arg, args):
    paren = await cg.get_variable(config[CONF_ID])
    var = cg.new_Pvariable(condition_id, template_arg, paren)

    if CONF_ABOVE in config:
        cg.add(var.set_min(config[CONF_ABOVE]))
    if CONF_BELOW in config:
        cg.add(var.set_max(config[CONF_BELOW]))

    return var


@coroutine_with_priority(40.0)
async def to_code(config):
    cg.add_define("USE_NUMBER")
    cg.add_global(number_ns.using)