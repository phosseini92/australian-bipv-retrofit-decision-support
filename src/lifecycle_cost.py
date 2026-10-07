"""Locked discounted whole-life-cost and replacement-cost bookkeeping."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from .input_loader import load_symbol_index
from .lifecycle_energy import LifecycleEnergyResult
from .replacement import scheduled_inverter_replacement_years


def _nonnegative_finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


def discount_factor(year: int, real_discount_rate: float) -> float:
    """Return the locked end-of-year discount factor ``1/(1+r)^year``."""

    if isinstance(year, bool) or not isinstance(year, int) or year < 0:
        raise ValueError("year must be a non-negative integer")
    rate = _nonnegative_finite("real_discount_rate", real_discount_rate)
    return 1.0 / ((1.0 + rate) ** year)


@dataclass(frozen=True)
class CostParameters:
    currency_basis: str
    horizon_years: int
    bipv_area_m2: float
    module_area_m2: float
    real_discount_rate: float
    reference_bipv_cost_per_m2: float
    direct_mount_cost_per_m2: float
    ventilated_complexity_factor: float
    ventilated_mount_cost_per_m2: float
    reversibility_premium_factor: float
    reversibility_premium_per_m2: float
    annual_om_rate: float
    cached_direct_annual_om_aud: float
    cached_ventilated_annual_om_aud: float
    inverter_replacement_factor: float
    inverter_service_life_years: int
    cost_table_inverter_year: int
    failure_rate_events_per_year: float
    failed_product_material_cost_per_event_aud: float
    assembly_extra_material_cost_per_event_aud: float
    eol_pv_mass_tonnes: float
    recycling_service_cost_per_tonne_aud: float
    eol_recycling_cost_aud: float
    transport_share: float
    transport_component_aud: float
    processing_component_aud: float
    owner_recovery_credit_per_tonne_aud: float
    total_owner_recovery_credit_aud: float
    central_access_cost_per_event_aud: float
    central_eol_removal_cost_aud: float
    access_input_label: str
    removal_input_label: str
    separate_transport_rule: str

    @classmethod
    def from_locked_inputs(cls) -> "CostParameters":
        rows = load_symbol_index()

        def number(symbol: str) -> float:
            value = rows[symbol].central
            if not hasattr(value, "as_tuple"):
                raise TypeError(f"locked input {symbol} is not numeric")
            result = float(value)
            if not math.isfinite(result):
                raise ValueError(f"locked input {symbol} is not finite")
            return result

        def integer(symbol: str) -> int:
            value = number(symbol)
            if not value.is_integer() or value < 1:
                raise ValueError(f"locked input {symbol} must be a positive integer")
            return int(value)

        access_label = str(rows["C_access"].central)
        removal_label = str(rows["C_EOL,rem"].central)
        transport_rule = str(rows["D_trans_cost"].central)
        if access_label != "BREAK-EVEN OUTPUT":
            raise ValueError("locked C_access label changed")
        if removal_label != "BREAK-EVEN / sensitivity":
            raise ValueError("locked C_EOL,rem label changed")
        if transport_rule != "Not added in baseline":
            raise ValueError("locked separate-transport rule changed")

        parameters = cls(
            currency_basis=str(rows["CUR"].central),
            horizon_years=integer("T"),
            bipv_area_m2=number("A_BIPV"),
            module_area_m2=number("A_mod"),
            real_discount_rate=number("r"),
            reference_bipv_cost_per_m2=number("C_BIPV"),
            direct_mount_cost_per_m2=number("C_direct"),
            ventilated_complexity_factor=number("p_vent"),
            ventilated_mount_cost_per_m2=number("C_vent"),
            reversibility_premium_factor=number("p_rev"),
            reversibility_premium_per_m2=number("ΔC_rev"),
            annual_om_rate=number("m_OM"),
            cached_direct_annual_om_aud=number("C_OM,dir"),
            cached_ventilated_annual_om_aud=number("C_OM,vent"),
            inverter_replacement_factor=number("p_invrep"),
            inverter_service_life_years=integer("SL_inv"),
            cost_table_inverter_year=integer("t_invrep"),
            failure_rate_events_per_year=number("f_fail"),
            failed_product_material_cost_per_event_aud=number("C_rep,mat"),
            assembly_extra_material_cost_per_event_aud=number("C_extra,asm"),
            eol_pv_mass_tonnes=number("M_EOL"),
            recycling_service_cost_per_tonne_aud=number("C_rec"),
            eol_recycling_cost_aud=number("C_EOL,rec"),
            transport_share=number("p_trans"),
            transport_component_aud=number("C_EOL,trans"),
            processing_component_aud=number("C_EOL,proc"),
            owner_recovery_credit_per_tonne_aud=number("V_rec"),
            total_owner_recovery_credit_aud=number("V_EOL"),
            # The specification explicitly excludes unsupported access and
            # removal tariffs from the central ranking. Zero here is an
            # accounting exclusion, not a claim that those services are free.
            central_access_cost_per_event_aud=0.0,
            central_eol_removal_cost_aud=0.0,
            access_input_label=access_label,
            removal_input_label=removal_label,
            separate_transport_rule=transport_rule,
        )
        parameters.validate_locked_derivations()
        return parameters

    def validate_locked_derivations(self, *, tolerance: float = 1e-12) -> None:
        checks = {
            "C_direct": (
                self.direct_mount_cost_per_m2,
                self.reference_bipv_cost_per_m2,
            ),
            "C_vent": (
                self.ventilated_mount_cost_per_m2,
                self.reference_bipv_cost_per_m2
                * (1.0 + self.ventilated_complexity_factor),
            ),
            "DeltaC_rev": (
                self.reversibility_premium_per_m2,
                self.reference_bipv_cost_per_m2
                * self.reversibility_premium_factor,
            ),
            "C_OM,dir": (
                self.cached_direct_annual_om_aud,
                self.bipv_area_m2
                * self.direct_mount_cost_per_m2
                * self.annual_om_rate,
            ),
            "C_OM,vent": (
                self.cached_ventilated_annual_om_aud,
                self.bipv_area_m2
                * self.ventilated_mount_cost_per_m2
                * self.annual_om_rate,
            ),
            "C_rep,mat": (
                self.failed_product_material_cost_per_event_aud,
                self.module_area_m2 * self.reference_bipv_cost_per_m2,
            ),
            "C_EOL,rec": (
                self.eol_recycling_cost_aud,
                self.eol_pv_mass_tonnes
                * self.recycling_service_cost_per_tonne_aud,
            ),
            "C_EOL,trans": (
                self.transport_component_aud,
                self.eol_recycling_cost_aud * self.transport_share,
            ),
            "C_EOL,proc": (
                self.processing_component_aud,
                self.eol_recycling_cost_aud - self.transport_component_aud,
            ),
            "V_EOL": (
                self.total_owner_recovery_credit_aud,
                self.eol_pv_mass_tonnes
                * self.owner_recovery_credit_per_tonne_aud,
            ),
        }
        failed = [
            symbol
            for symbol, (locked, calculated) in checks.items()
            if not math.isclose(
                locked,
                calculated,
                rel_tol=tolerance,
                abs_tol=tolerance,
            )
        ]
        if failed:
            raise ValueError(f"locked cost derivations changed: {failed}")
        if self.inverter_service_life_years != self.cost_table_inverter_year:
            raise ValueError("SL_inv and t_invrep differ")
        if self.assembly_extra_material_cost_per_event_aud != 0.0:
            raise ValueError("assembly adjacent-product material cost is not zero")
        if self.central_access_cost_per_event_aud != 0.0:
            raise ValueError("central access cost must remain excluded")
        if self.central_eol_removal_cost_aud != 0.0:
            raise ValueError("central EoL removal cost must remain excluded")


@dataclass(frozen=True)
class ReplacementCostBookkeeping:
    event_material_cost_aud: float
    annual_expected_material_cost_aud: float
    assembly_extra_material_cost_per_event_aud: float
    access_cost_per_event_aud: float
    annual_expected_access_cost_aud: float


@dataclass(frozen=True)
class AnnualCostFlow:
    year: int
    discount_factor: float
    om_aud: float
    corrective_material_aud: float
    access_aud: float
    inverter_aud: float
    eol_net_aud: float
    nominal_total_aud: float
    discounted_total_aud: float


@dataclass(frozen=True)
class LifecycleCostResult:
    variant_id: str
    short_code: str
    mounting: str
    connection: str
    replacement_scope: str
    mounting_initial_cost_aud: float
    reversibility_premium_aud: float
    initial_cost_aud: float
    annual_om_cost_aud: float
    replacement: ReplacementCostBookkeeping
    inverter_reference_cost_per_event_aud: float
    inverter_replacement_years: tuple[int, ...]
    eol_recycling_cost_aud: float
    eol_removal_cost_aud: float
    owner_recovery_credit_aud: float
    eol_net_cost_aud: float
    pv_om_aud: float
    pv_corrective_material_aud: float
    pv_access_aud: float
    pv_inverter_aud: float
    pv_eol_net_aud: float
    whole_life_cost_aud: float
    lifetime_energy_kwh: float
    cost_intensity_aud_per_kwh: float
    annual: tuple[AnnualCostFlow, ...]

    def as_record(self) -> dict[str, Any]:
        return {
            "id": self.variant_id,
            "short_code": self.short_code,
            "mounting": self.mounting,
            "connection": self.connection,
            "replacement_scope": self.replacement_scope,
            "C_mount_initial_aud": self.mounting_initial_cost_aud,
            "C_rev_aud": self.reversibility_premium_aud,
            "C0_aud": self.initial_cost_aud,
            "C_OM_annual_aud": self.annual_om_cost_aud,
            "C_rep_event_aud": self.replacement.event_material_cost_aud,
            "C_corr_material_annual_aud": (
                self.replacement.annual_expected_material_cost_aud
            ),
            "C_extra_assembly_event_aud": (
                self.replacement.assembly_extra_material_cost_per_event_aud
            ),
            "C_access_event_aud": self.replacement.access_cost_per_event_aud,
            "C_access_annual_aud": (
                self.replacement.annual_expected_access_cost_aud
            ),
            "C_inv_ref_event_aud": (
                self.inverter_reference_cost_per_event_aud
            ),
            "inverter_replacement_years": list(
                self.inverter_replacement_years
            ),
            "C_EOL_recycling_aud": self.eol_recycling_cost_aud,
            "C_EOL_removal_aud": self.eol_removal_cost_aud,
            "V_owner_aud": self.owner_recovery_credit_aud,
            "C_EOL_net_aud": self.eol_net_cost_aud,
            "PV_OM_aud": self.pv_om_aud,
            "PV_corrective_material_aud": self.pv_corrective_material_aud,
            "PV_access_aud": self.pv_access_aud,
            "PV_inverter_aud": self.pv_inverter_aud,
            "PV_EOL_net_aud": self.pv_eol_net_aud,
            "WLC_aud": self.whole_life_cost_aud,
            "E_life_kwh": self.lifetime_energy_kwh,
            "CostIntensity_aud_per_kwh": (
                self.cost_intensity_aud_per_kwh
            ),
        }


def _mount_cost_per_m2(
    mounting: str,
    parameters: CostParameters,
) -> float:
    if mounting == "direct":
        return parameters.direct_mount_cost_per_m2
    if mounting == "ventilated":
        return parameters.ventilated_mount_cost_per_m2
    raise ValueError(f"unapproved mounting: {mounting!r}")


def _is_reversible(connection: str) -> bool:
    if connection == "low_reversibility":
        return False
    if connection == "reversible_mechanical":
        return True
    raise ValueError(f"unapproved connection: {connection!r}")


def run_variant_lifecycle_cost(
    variant: Mapping[str, Any],
    lifecycle: LifecycleEnergyResult,
    *,
    parameters: CostParameters | None = None,
) -> LifecycleCostResult:
    """Calculate central WLC without monetising lifetime electricity."""

    parameters = parameters or CostParameters.from_locked_inputs()
    parameters.validate_locked_derivations()
    required = {"id", "short_code", "mounting", "connection", "replacement_scope"}
    missing = required - set(variant)
    if missing:
        raise ValueError(f"variant is missing fields: {sorted(missing)}")
    identity = (
        str(variant["id"]),
        str(variant["short_code"]),
        str(variant["mounting"]),
        str(variant["connection"]),
        str(variant["replacement_scope"]),
    )
    lifecycle_identity = (
        lifecycle.variant_id,
        lifecycle.short_code,
        lifecycle.mounting,
        lifecycle.connection,
        lifecycle.replacement_scope,
    )
    if identity != lifecycle_identity:
        raise ValueError("variant and lifecycle result identities differ")
    if len(lifecycle.annual) != parameters.horizon_years:
        raise ValueError("lifecycle and cost horizons differ")

    mounting_cost = (
        parameters.bipv_area_m2
        * _mount_cost_per_m2(str(variant["mounting"]), parameters)
    )
    reversibility_premium = (
        parameters.bipv_area_m2 * parameters.reversibility_premium_per_m2
        if _is_reversible(str(variant["connection"]))
        else 0.0
    )
    initial_cost = mounting_cost + reversibility_premium
    annual_om = parameters.annual_om_rate * initial_cost
    annual_corrective_material = (
        parameters.failure_rate_events_per_year
        * parameters.failed_product_material_cost_per_event_aud
    )
    annual_access = (
        parameters.failure_rate_events_per_year
        * parameters.central_access_cost_per_event_aud
    )
    replacement = ReplacementCostBookkeeping(
        event_material_cost_aud=(
            parameters.failed_product_material_cost_per_event_aud
        ),
        annual_expected_material_cost_aud=annual_corrective_material,
        assembly_extra_material_cost_per_event_aud=(
            parameters.assembly_extra_material_cost_per_event_aud
        ),
        access_cost_per_event_aud=(
            parameters.central_access_cost_per_event_aud
        ),
        annual_expected_access_cost_aud=annual_access,
    )

    inverter_cost = (
        parameters.inverter_replacement_factor
        * parameters.bipv_area_m2
        * parameters.reference_bipv_cost_per_m2
    )
    inverter_years = scheduled_inverter_replacement_years(
        parameters.horizon_years,
        parameters.inverter_service_life_years,
    )
    if inverter_years != lifecycle.inverter_replacement_years:
        raise ValueError("lifecycle and cost inverter schedules differ")

    eol_recycling = parameters.eol_recycling_cost_aud
    eol_removal = parameters.central_eol_removal_cost_aud
    owner_recovery = parameters.total_owner_recovery_credit_aud
    eol_net = eol_recycling + eol_removal - owner_recovery

    annual: list[AnnualCostFlow] = []
    for year in range(1, parameters.horizon_years + 1):
        factor = discount_factor(year, parameters.real_discount_rate)
        inverter = inverter_cost if year in inverter_years else 0.0
        eol = eol_net if year == parameters.horizon_years else 0.0
        nominal_total = (
            annual_om
            + annual_corrective_material
            + annual_access
            + inverter
            + eol
        )
        annual.append(
            AnnualCostFlow(
                year=year,
                discount_factor=factor,
                om_aud=annual_om,
                corrective_material_aud=annual_corrective_material,
                access_aud=annual_access,
                inverter_aud=inverter,
                eol_net_aud=eol,
                nominal_total_aud=nominal_total,
                discounted_total_aud=nominal_total * factor,
            )
        )

    annual_tuple = tuple(annual)
    pv_om = sum(item.om_aud * item.discount_factor for item in annual_tuple)
    pv_corrective = sum(
        item.corrective_material_aud * item.discount_factor
        for item in annual_tuple
    )
    pv_access = sum(
        item.access_aud * item.discount_factor for item in annual_tuple
    )
    pv_inverter = sum(
        item.inverter_aud * item.discount_factor for item in annual_tuple
    )
    pv_eol = sum(
        item.eol_net_aud * item.discount_factor for item in annual_tuple
    )
    whole_life_cost = (
        initial_cost
        + pv_om
        + pv_corrective
        + pv_access
        + pv_inverter
        + pv_eol
    )
    lifetime_energy = _nonnegative_finite(
        "lifetime_energy_kwh", lifecycle.net_lifetime_energy_kwh
    )
    if lifetime_energy == 0.0:
        raise ValueError("lifetime_energy_kwh must be greater than zero")
    return LifecycleCostResult(
        variant_id=identity[0],
        short_code=identity[1],
        mounting=identity[2],
        connection=identity[3],
        replacement_scope=identity[4],
        mounting_initial_cost_aud=mounting_cost,
        reversibility_premium_aud=reversibility_premium,
        initial_cost_aud=initial_cost,
        annual_om_cost_aud=annual_om,
        replacement=replacement,
        inverter_reference_cost_per_event_aud=inverter_cost,
        inverter_replacement_years=inverter_years,
        eol_recycling_cost_aud=eol_recycling,
        eol_removal_cost_aud=eol_removal,
        owner_recovery_credit_aud=owner_recovery,
        eol_net_cost_aud=eol_net,
        pv_om_aud=pv_om,
        pv_corrective_material_aud=pv_corrective,
        pv_access_aud=pv_access,
        pv_inverter_aud=pv_inverter,
        pv_eol_net_aud=pv_eol,
        whole_life_cost_aud=whole_life_cost,
        lifetime_energy_kwh=lifetime_energy,
        cost_intensity_aud_per_kwh=whole_life_cost / lifetime_energy,
        annual=annual_tuple,
    )


def run_lifecycle_cost(
    variants: Sequence[Mapping[str, Any]],
    lifecycle_results: Sequence[LifecycleEnergyResult],
    *,
    parameters: CostParameters | None = None,
) -> tuple[LifecycleCostResult, ...]:
    """Run the locked central WLC equations for V01–V08."""

    parameters = parameters or CostParameters.from_locked_inputs()
    lifecycle_by_id = {item.variant_id: item for item in lifecycle_results}
    if len(lifecycle_by_id) != len(lifecycle_results):
        raise ValueError("duplicate lifecycle result id")
    results: list[LifecycleCostResult] = []
    for variant in variants:
        variant_id = str(variant.get("id"))
        if variant_id not in lifecycle_by_id:
            raise ValueError(f"missing lifecycle result for {variant_id!r}")
        results.append(
            run_variant_lifecycle_cost(
                variant,
                lifecycle_by_id[variant_id],
                parameters=parameters,
            )
        )
    return tuple(results)


IMPLEMENTATION_STATUS = "IMPLEMENTED_INTEGRATION_GATE"
