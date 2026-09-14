"""User-contributed protocol for Huawei product 2OIB.

小青芒千分比深度调光线性灯 (HC-DDD-002) — WiFi 灯带/线性灯
Profile: https://smarthome-drcn.dbankcdn.com/device/guide/2OIB/2OIB.json

Services used:
  switch      on                 bool 0/1
  brightness  brightness         int 1..100 (%)
  cct         colorTemperature   int 2000..6500 (K)
  lightMode   mode               enum 0..10 (场景模式)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_COLOUR_MODE_COLOR_TEMP = "color_temp"


def _service(profile: Mapping[str, Any], sid: str) -> Mapping[str, Any] | None:
    for service in profile.get("services", ()):
        if isinstance(service, Mapping) and service.get("serviceId") == sid:
            return service
    return None


def _field(
    profile: Mapping[str, Any],
    sid: str,
    name: str,
) -> Mapping[str, Any] | None:
    service = _service(profile, sid)
    if service is None:
        return None
    for field in service.get("characteristics", ()):
        if isinstance(field, Mapping) and field.get("characteristicName") == name:
            return field
    return None


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _profile_range(field: Mapping[str, Any]) -> tuple[float, float] | None:
    minimum = _number(field.get("min"))
    maximum = _number(field.get("max"))
    if minimum is None or maximum is None or maximum <= minimum:
        return None
    return float(minimum), float(maximum)


def _profile_step(field: Mapping[str, Any]) -> float | None:
    step = _number(field.get("step"))
    if step is None or step <= 0:
        return None
    return float(step)


def _device_brightness_to_ha(
    value: Any,
    field: Mapping[str, Any],
) -> int | None:
    """Convert a product brightness value (1..100 %) to HA's 0..255 scale."""

    number = _number(value)
    value_range = _profile_range(field)
    if number is None or value_range is None:
        return None
    minimum, maximum = value_range
    number = min(max(float(number), minimum), maximum)
    return round((number - minimum) * 255 / (maximum - minimum))


def _ha_brightness_to_device(
    value: Any,
    field: Mapping[str, Any],
) -> int | float:
    """Convert HA's 0..255 brightness to the product Profile range (1..100)."""

    number = _number(value)
    value_range = _profile_range(field)
    if number is None or value_range is None:
        raise ValueError("2OIB brightness range is missing from the Profile")
    minimum, maximum = value_range
    number = min(max(float(number), 0.0), 255.0)
    device_value = minimum + number * (maximum - minimum) / 255
    step = _profile_step(field)
    if step is not None:
        device_value = minimum + round((device_value - minimum) / step) * step
    if (field.get("characteristicType") or "").casefold() in {
        "int",
        "integer",
    }:
        return int(round(device_value))
    return device_value


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.casefold() in {"1", "true", "on"}:
            return True
        if value.casefold() in {"0", "false", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _coerce_profile_value(
    value: Any,
    field: Mapping[str, Any] | None,
) -> Any:
    """Encode a Profile value using its declared characteristic type."""

    data_type = str((field or {}).get("characteristicType") or "").casefold()
    if data_type in {"int", "integer", "enum"}:
        number = _number(value)
        if number is not None:
            return int(number) if float(number).is_integer() else number
    if data_type in {"float", "double", "number"}:
        number = _number(value)
        if number is not None:
            return float(number)
    if not data_type:
        number = _number(value)
        if number is not None:
            return number
    return value


async def _turn_on(context: DeviceContext, data: Mapping[str, Any]) -> None:
    await context.async_send_service("switch", {"on": 1})
    if data.get("brightness") is not None:
        brightness_field = _field(
            context.profile or {},
            "brightness",
            "brightness",
        )
        if brightness_field is None:
            raise ValueError("2OIB brightness field is missing from the Profile")
        await context.async_send_service(
            "brightness",
            {
                "brightness": _ha_brightness_to_device(
                    data["brightness"],
                    brightness_field,
                )
            },
        )
    if data.get("color_temp_kelvin") is not None:
        cct_field = _field(context.profile or {}, "cct", "colorTemperature")
        if cct_field is None:
            raise ValueError("2OIB cct field is missing from the Profile")
        value_range = _profile_range(cct_field)
        kelvin = _number(data["color_temp_kelvin"])
        if value_range is not None and kelvin is not None:
            minimum, maximum = value_range
            kelvin = min(max(kelvin, minimum), maximum)
        await context.async_send_service(
            "cct",
            {"colorTemperature": _coerce_profile_value(kelvin, cct_field)},
        )


async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("switch", {"on": 0})


async def _select_light_mode(
    context: DeviceContext,
    data: Mapping[str, Any],
) -> None:
    profile = context.profile or {}
    field = _field(profile, "lightMode", "mode") or {}
    for option in (field or {}).get("enumList", ()):
        if not isinstance(option, Mapping):
            continue
        label = str(option.get("descCh") or option.get("enumVal"))
        if label == data["option"]:
            await context.async_send_service(
                "lightMode",
                {
                    "mode": _coerce_profile_value(
                        option.get("enumVal"),
                        field,
                    )
                },
            )
            return
    raise ValueError(f"unknown light mode: {data['option']}")


class Product2OIBAdapter:
    """Keep all 2OIB entity and command choices in this file."""

    prod_id = "2OIB"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None or not all(
            context.has_service(sid)
            for sid in ("switch", "brightness", "cct")
        ):
            return ()

        brightness = _field(profile, "brightness", "brightness") or {}
        cct = _field(profile, "cct", "colorTemperature") or {}
        light_actions = {
            "turn_on": _turn_on,
            "turn_off": _turn_off,
        }

        def light_state(device: DeviceContext) -> Mapping[str, Any]:
            is_on = _bool(device.value("switch", "on"))
            color_temp = _number(device.value("cct", "colorTemperature"))
            return {
                "is_on": is_on,
                "brightness": _device_brightness_to_ha(
                    device.value("brightness", "brightness"),
                    brightness,
                ),
                "color_temp_kelvin": color_temp if is_on else None,
                "color_mode": (
                    _COLOUR_MODE_COLOR_TEMP
                    if is_on and color_temp is not None
                    else None
                ),
            }

        entities = [
            EntitySpec(
                platform="light",
                key="light",
                name="灯",
                state=light_state,
                metadata={
                    "supported_color_modes": {_COLOUR_MODE_COLOR_TEMP},
                    "min_color_temp_kelvin": cct.get("min"),
                    "max_color_temp_kelvin": cct.get("max"),
                },
                actions=light_actions,
            )
        ]

        if context.has_service("lightMode"):
            mode_field = _field(profile, "lightMode", "mode") or {}
            options = tuple(
                (
                    str(option.get("descCh") or option.get("enumVal")),
                    option.get("enumVal"),
                )
                for option in mode_field.get("enumList", ())
                if isinstance(option, Mapping)
            )

            def mode_state(device: DeviceContext) -> Mapping[str, Any]:
                value = _number(device.value("lightMode", "mode"))
                if value is None:
                    return {"current_option": None}
                current_option = next(
                    (label for label, raw in options if str(raw) == str(value)),
                    str(value),
                )
                return {"current_option": current_option}

            entities.append(
                EntitySpec(
                    platform="select",
                    key="light_mode",
                    name="灯光模式",
                    state=mode_state,
                    metadata={"options": tuple(label for label, _ in options)},
                    actions={"select_option": _select_light_mode},
                )
            )
        return tuple(entities)


ADAPTER = Product2OIBAdapter()
