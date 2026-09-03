import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal

from app.models.procurement_opportunities import RequirementStrength
from app.models.profile_capabilities import CapabilityState, ProfileSectionState
from app.schemas.procurement_matching import (
    MATCH_DIMENSION_ORDER,
    AtomicMatchState,
    DimensionMatchState,
    EquipmentSnapshot,
    MatchAtomResult,
    MatchDimension,
    MatchDimensionResult,
    MatchEvaluationContext,
    MatchFact,
    MatchResult,
    MatchSeverity,
    OpportunityMatchIdentity,
    PairMatchVerdict,
    ProfileMatchingSnapshot,
    UnknownOrigin,
)
from app.schemas.procurement_opportunities import (
    PreparedOpportunityInput,
    canonical_payload,
    canonicalize_opportunity,
)

_REASONS: dict[str, str] = {
    "PROCUREMENT_REQUIREMENT_UNKNOWN": (
        "The procurement source did not declare whether this requirement exists."
    ),
    "PROCUREMENT_REQUIREMENT_NOT_APPLICABLE": (
        "The procurement source explicitly declared no requirement in this dimension."
    ),
    "MISSING_PROFILE_CAPABILITY_OKPD2_MAPPING": (
        "The profile domain has no approved Product-to-OKPD2 capability mapping."
    ),
    "PRODUCT_TYPE_EXPERIENCE_MATCH": (
        "An exact product type exists in the profile product catalog."
    ),
    "PRODUCT_TYPE_EXPERIENCE_MISMATCH": (
        "The populated profile product catalog has no exact product type match."
    ),
    "PROFILE_PRODUCT_CATALOG_NOT_DECLARED": (
        "The empty profile product catalog has no completeness declaration."
    ),
    "CAPABILITY_EXPLICIT_SUPPORTED": "The exact resolved capability is SUPPORTED.",
    "CAPABILITY_EXPLICIT_UNSUPPORTED": (
        "The exact resolved capability is explicitly UNSUPPORTED."
    ),
    "HARD_MATERIAL_EXPLICIT_UNSUPPORTED": (
        "A single mandatory material target is explicitly UNSUPPORTED for the "
        "current in-house production profile."
    ),
    "HARD_TECHNOLOGY_EXPLICIT_UNSUPPORTED": (
        "A single mandatory technology target is explicitly UNSUPPORTED for the "
        "current in-house production profile."
    ),
    "CAPABILITY_EXPLICIT_UNKNOWN": (
        "The exact resolved capability is explicitly UNKNOWN."
    ),
    "CAPABILITY_NOT_ASSERTED_COMPLETE_SECTION": (
        "The target is absent from a CONFIRMED_COMPLETE capability section."
    ),
    "CAPABILITY_NOT_ASSERTED_INCOMPLETE_SECTION": (
        "The target is not asserted and the capability section is not complete."
    ),
    "AMBIGUOUS_REQUIREMENT_GROUPING": (
        "Multiple requirements have no declared ALL_OF, ANY_OF, or grouping semantics."
    ),
    "EQUIPMENT_TYPE_PRESENT": "An exact equipment type is recorded in the profile.",
    "PROFILE_EQUIPMENT_NOT_DECLARED": (
        "No exact equipment type is recorded and equipment completeness is unavailable."
    ),
    "EQUIPMENT_CNC_PRESENT": "A matching equipment candidate records cnc=True.",
    "PROFILE_EQUIPMENT_CNC_NOT_PROVEN": (
        "No matching candidate proves cnc=True; technical False is not "
        "negative evidence."
    ),
    "AMBIGUOUS_CNC_FALSE_SEMANTICS": (
        "Procurement cnc=False has no approved requirement semantics in Slice A."
    ),
    "EQUIPMENT_AXES_SATISFIED": (
        "A matching equipment candidate has at least the required number of axes."
    ),
    "PROFILE_EQUIPMENT_AXES_NOT_PROVEN": (
        "Recorded matching equipment does not prove the required axes capability."
    ),
    "PROFILE_EQUIPMENT_UNIT_NOT_DECLARED": (
        "Profile equipment dimensional units are not declared for comparison."
    ),
    "MISSING_PROFILE_CAPABILITY_MAX_WORKPIECE_MASS": (
        "The profile has no approved maximum workpiece mass capability."
    ),
    "AMBIGUOUS_DIMENSIONAL_ENVELOPE_SEMANTICS": (
        "Profile dimensional units, orientation, and equipment linkage are "
        "not approved."
    ),
    "QUALITY_IT_GRADE_MATCH": "The profile IT grade satisfies the requested grade.",
    "QUALITY_IT_GRADE_MISMATCH": (
        "The declared profile IT grade is worse than the requested grade."
    ),
    "PROFILE_QUALITY_IT_GRADE_NOT_DECLARED": (
        "The profile has no declared IT grade capability."
    ),
    "QUALITY_MEASURING_CAPABILITY_PRESENT": (
        "The profile records measuring_tools=True."
    ),
    "PROFILE_QUALITY_MEASURING_CAPABILITY_NOT_PROVEN": (
        "The profile does not prove measuring capability; technical False is "
        "not negative."
    ),
    "QUALITY_MEASURING_CAPABILITY_NOT_REQUIRED": (
        "The procurement requirement explicitly does not require measuring capability."
    ),
    "PROFILE_QUALITY_UNIT_NOT_DECLARED": (
        "The unit of profile min_ra is not declared as procurement micrometres."
    ),
    "AMBIGUOUS_CMM_CAPABILITY_MAPPING": (
        "The mapping from procurement cmm_required to profile cim_machine is "
        "unapproved."
    ),
    "CERTIFICATE_TYPE_CURRENTLY_VALID": (
        "An exact certificate type is valid on the explicit evaluation date."
    ),
    "PROFILE_CURRENT_CERTIFICATE_NOT_PROVEN": (
        "No exact currently-valid certificate is recorded and completeness is "
        "unavailable."
    ),
    "AMBIGUOUS_CERTIFICATE_REQUIRED_BY_SEMANTICS": (
        "The business meaning of certificate required_by is not approved for matching."
    ),
    "AMBIGUOUS_CERTIFICATE_VALID_THROUGH_SEMANTICS": (
        "The business meaning of certificate valid_through is not approved "
        "for matching."
    ),
}


def _json_default(value: object) -> str:
    if isinstance(value, (date, Decimal)):
        return str(value)
    raise TypeError(f"Unsupported canonical matching value: {type(value)!r}")


class ProcurementMatchingEngine:
    """Pure deterministic Slice A capability matcher."""

    def match(
        self,
        opportunity_id: int,
        opportunity: PreparedOpportunityInput,
        profile: ProfileMatchingSnapshot,
        context: MatchEvaluationContext,
    ) -> MatchResult:
        opportunity = canonicalize_opportunity(opportunity)
        evaluators: dict[
            MatchDimension,
            Callable[[], MatchDimensionResult],
        ] = {
            MatchDimension.OKPD2_CODES: lambda: self._okpd2(opportunity),
            MatchDimension.PRODUCT_TYPE_CODES: lambda: self._products(
                opportunity, profile
            ),
            MatchDimension.MATERIAL_REQUIREMENTS: lambda: self._materials(
                opportunity, profile
            ),
            MatchDimension.TECHNOLOGY_REQUIREMENTS: lambda: self._technologies(
                opportunity, profile
            ),
            MatchDimension.EQUIPMENT_REQUIREMENTS: lambda: self._equipment(
                opportunity, profile
            ),
            MatchDimension.DIMENSIONAL_MASS_REQUIREMENTS: lambda: self._dimensions(
                opportunity
            ),
            MatchDimension.QUALITY_REQUIREMENTS: lambda: self._quality(
                opportunity, profile
            ),
            MatchDimension.REQUIRED_CERTIFICATES: lambda: self._certificates(
                opportunity, profile, context.evaluation_date
            ),
        }
        dimensions = tuple(
            evaluators[dimension]() for dimension in MATCH_DIMENSION_ORDER
        )
        atoms = tuple(atom for item in dimensions for atom in item.atoms)
        hard_ids = tuple(
            sorted(
                atom.evidence_id
                for atom in atoms
                if atom.severity == MatchSeverity.HARD
            )
        )
        verdict = self._verdict(atoms, hard_ids)
        return MatchResult(
            opportunity_id=opportunity_id,
            opportunity_identity=OpportunityMatchIdentity(
                source=opportunity.source,
                external_id=opportunity.external_id,
            ),
            profile_id=profile.profile_id,
            ruleset_version=context.ruleset_version,
            evaluation_date=context.evaluation_date,
            input_fingerprint=self._fingerprint(opportunity, profile, context),
            verdict=verdict,
            dimensions=dimensions,
            hard_incompatibility_evidence_ids=hard_ids,
        )

    @staticmethod
    def _fingerprint(
        opportunity: PreparedOpportunityInput,
        profile: ProfileMatchingSnapshot,
        context: MatchEvaluationContext,
    ) -> str:
        profile_payload = profile.model_dump(mode="json")
        sort_keys = {
            "products": lambda item: (item["product_type_code"], item["product_id"]),
            "technology_capabilities": lambda item: (
                item["technology_code"],
                item["capability_id"],
            ),
            "material_capabilities": lambda item: (
                item["material_group_code"] or "",
                item["material_id"] or -1,
                item["capability_id"],
            ),
            "equipments": lambda item: (
                item["equipment_type_code"],
                item["equipment_id"],
            ),
            "certificates": lambda item: (
                item["certificate_type_code"],
                item["issue_date"],
                item["expiry_date"],
                item["certificate_id"],
            ),
        }
        for name, key in sort_keys.items():
            profile_payload[name] = sorted(profile_payload[name], key=key)
        payload = {
            "opportunity": {
                "source": opportunity.source,
                "external_id": opportunity.external_id,
                "payload": canonical_payload(opportunity),
            },
            "profile": profile_payload,
            "evaluation_date": context.evaluation_date.isoformat(),
            "ruleset_version": context.ruleset_version,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=_json_default,
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _verdict(
        atoms: tuple[MatchAtomResult, ...],
        hard_ids: tuple[str, ...],
    ) -> PairMatchVerdict:
        if hard_ids:
            return PairMatchVerdict.HARD_INCOMPATIBLE
        if any(atom.reason_code == "AMBIGUOUS_REQUIREMENT_GROUPING" for atom in atoms):
            return PairMatchVerdict.UNDETERMINED
        mandatory = [
            atom
            for atom in atoms
            if atom.requirement_strength == RequirementStrength.MANDATORY
            and atom.state != AtomicMatchState.NOT_APPLICABLE
        ]
        if any(atom.state != AtomicMatchState.MATCH for atom in mandatory):
            return PairMatchVerdict.UNDETERMINED
        if any(atom.state == AtomicMatchState.MATCH for atom in atoms):
            return PairMatchVerdict.DETERMINATE_MATCH
        return PairMatchVerdict.UNDETERMINED

    @classmethod
    def _atom(
        cls,
        dimension: MatchDimension,
        target_key: str,
        subfield: str,
        requirement_path: str,
        requirement_value: str | int | bool | Decimal | date | None,
        state: AtomicMatchState,
        severity: MatchSeverity,
        reason_code: str,
        *,
        origin: UnknownOrigin | None = None,
        capability_path: str | None = None,
        capability_value: str | int | bool | Decimal | date | None = None,
        resolution_path: Sequence[str] = (),
        strength: RequirementStrength | None = None,
    ) -> MatchAtomResult:
        identity = json.dumps(
            {
                "dimension": dimension.value,
                "target": target_key,
                "subfield": subfield,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return MatchAtomResult(
            evidence_id=hashlib.sha256(identity.encode()).hexdigest(),
            dimension=dimension,
            target_key=target_key,
            subfield=subfield,
            requirement_path=requirement_path,
            requirement=MatchFact(path=requirement_path, value=requirement_value),
            capability_path=capability_path,
            capability=(
                MatchFact(path=capability_path, value=capability_value)
                if capability_path is not None
                else None
            ),
            state=state,
            severity=severity,
            reason_code=reason_code,
            reason=_REASONS[reason_code],
            origin=origin,
            resolution_path=tuple(resolution_path),
            requirement_strength=strength,
        )

    @classmethod
    def _collection_boundary(
        cls,
        dimension: MatchDimension,
        values: list[object] | None,
    ) -> MatchDimensionResult | None:
        path = dimension.value
        if values is None:
            atom = cls._atom(
                dimension,
                "__collection__",
                "collection",
                path,
                None,
                AtomicMatchState.UNKNOWN,
                MatchSeverity.UNRESOLVED,
                "PROCUREMENT_REQUIREMENT_UNKNOWN",
                origin=UnknownOrigin.PROCUREMENT_SOURCE,
            )
            return cls._dimension(dimension, [atom])
        if not values:
            atom = cls._atom(
                dimension,
                "__collection__",
                "collection",
                path,
                "[]",
                AtomicMatchState.NOT_APPLICABLE,
                MatchSeverity.NOT_APPLICABLE,
                "PROCUREMENT_REQUIREMENT_NOT_APPLICABLE",
            )
            return cls._dimension(dimension, [atom])
        return None

    @classmethod
    def _ambiguity(
        cls,
        dimension: MatchDimension,
        count: int,
    ) -> MatchAtomResult:
        return cls._atom(
            dimension,
            "__collection__",
            "grouping",
            dimension.value,
            count,
            AtomicMatchState.UNKNOWN,
            MatchSeverity.UNRESOLVED,
            "AMBIGUOUS_REQUIREMENT_GROUPING",
            origin=UnknownOrigin.AMBIGUOUS_DOMAIN_SEMANTICS,
        )

    @staticmethod
    def _dimension(
        dimension: MatchDimension,
        atoms: Sequence[MatchAtomResult],
    ) -> MatchDimensionResult:
        deduplicated = {atom.evidence_id: atom for atom in atoms}
        ordered = tuple(
            sorted(
                deduplicated.values(),
                key=lambda atom: (
                    atom.target_key,
                    atom.subfield,
                    atom.reason_code,
                    atom.evidence_id,
                ),
            )
        )
        states = [atom.state for atom in ordered]
        applicable = [
            state for state in states if state != AtomicMatchState.NOT_APPLICABLE
        ]
        determinate = [
            state
            for state in applicable
            if state in {AtomicMatchState.MATCH, AtomicMatchState.MISMATCH}
        ]
        if not applicable:
            state = DimensionMatchState.NOT_APPLICABLE
        elif not determinate:
            state = DimensionMatchState.UNKNOWN
        elif any(item == AtomicMatchState.UNKNOWN for item in applicable):
            state = DimensionMatchState.PARTIAL
        elif all(item == AtomicMatchState.MATCH for item in applicable):
            state = DimensionMatchState.MATCH
        elif all(item == AtomicMatchState.MISMATCH for item in applicable):
            state = DimensionMatchState.MISMATCH
        else:
            state = DimensionMatchState.PARTIAL
        return MatchDimensionResult(
            dimension=dimension,
            state=state,
            atoms=ordered,
            reason_codes=tuple(sorted({atom.reason_code for atom in ordered})),
        )

    def _okpd2(self, opportunity: PreparedOpportunityInput) -> MatchDimensionResult:
        dimension = MatchDimension.OKPD2_CODES
        boundary = self._collection_boundary(dimension, opportunity.okpd2_codes)
        if boundary:
            return boundary
        codes = opportunity.okpd2_codes or []
        atoms: list[MatchAtomResult] = []
        if len(codes) > 1:
            atoms.append(self._ambiguity(dimension, len(codes)))
        for index, code in enumerate(codes):
            atoms.append(
                self._atom(
                    dimension,
                    code,
                    "code",
                    f"okpd2_codes[{index}]",
                    code,
                    AtomicMatchState.UNKNOWN,
                    MatchSeverity.UNRESOLVED,
                    "MISSING_PROFILE_CAPABILITY_OKPD2_MAPPING",
                    origin=UnknownOrigin.MISSING_PROFILE_CAPABILITY,
                )
            )
        return self._dimension(dimension, atoms)

    def _products(
        self,
        opportunity: PreparedOpportunityInput,
        profile: ProfileMatchingSnapshot,
    ) -> MatchDimensionResult:
        dimension = MatchDimension.PRODUCT_TYPE_CODES
        boundary = self._collection_boundary(dimension, opportunity.product_type_codes)
        if boundary:
            return boundary
        codes = opportunity.product_type_codes or []
        products = sorted(
            profile.products,
            key=lambda item: (item.product_type_code, item.product_id),
        )
        atoms: list[MatchAtomResult] = []
        if len(codes) > 1:
            atoms.append(self._ambiguity(dimension, len(codes)))
        for index, code in enumerate(codes):
            matches = [item for item in products if item.product_type_code == code]
            if matches:
                state = AtomicMatchState.MATCH
                severity = MatchSeverity.SOFT
                reason = "PRODUCT_TYPE_EXPERIENCE_MATCH"
                origin = None
            elif products:
                state = AtomicMatchState.MISMATCH
                severity = MatchSeverity.SOFT
                reason = "PRODUCT_TYPE_EXPERIENCE_MISMATCH"
                origin = None
            else:
                state = AtomicMatchState.UNKNOWN
                severity = MatchSeverity.UNRESOLVED
                reason = "PROFILE_PRODUCT_CATALOG_NOT_DECLARED"
                origin = UnknownOrigin.ENTERPRISE_PROFILE
            atoms.append(
                self._atom(
                    dimension,
                    code,
                    "product_type_code",
                    f"product_type_codes[{index}]",
                    code,
                    state,
                    severity,
                    reason,
                    origin=origin,
                    capability_path="profile.products.product_type_code",
                    capability_value=code if matches else None,
                    resolution_path=[f"product:{item.product_id}" for item in matches],
                )
            )
        return self._dimension(dimension, atoms)

    def _materials(
        self,
        opportunity: PreparedOpportunityInput,
        profile: ProfileMatchingSnapshot,
    ) -> MatchDimensionResult:
        dimension = MatchDimension.MATERIAL_REQUIREMENTS
        items = opportunity.material_requirements
        boundary = self._collection_boundary(dimension, items)
        if boundary:
            return boundary
        ambiguous = len(items or []) > 1
        atoms: list[MatchAtomResult] = []
        if ambiguous:
            atoms.append(self._ambiguity(dimension, len(items or [])))
        capabilities = sorted(
            profile.material_capabilities,
            key=lambda cap: (
                cap.material_group_code or "",
                cap.material_id or -1,
                cap.capability_id,
            ),
        )
        for index, item in enumerate(items or []):
            target = (
                f"material:{item.material_id}"
                if item.material_id is not None
                else f"group:{item.material_group_code}"
            )
            exact = next(
                (
                    cap
                    for cap in capabilities
                    if item.material_id is not None
                    and cap.material_id == item.material_id
                ),
                None,
            )
            group = next(
                (
                    cap
                    for cap in capabilities
                    if cap.material_group_code == item.material_group_code
                ),
                None,
            )
            resolved = exact or group
            resolution = (
                [f"material_capability:{resolved.capability_id}"]
                if resolved is not None
                else ["NO_ASSERTION"]
            )
            atoms.append(
                self._state_capability_atom(
                    dimension=dimension,
                    target=target,
                    requirement_path=f"material_requirements[{index}]",
                    requirement_value=(
                        item.material_id
                        if item.material_id is not None
                        else item.material_group_code
                    ),
                    capability_path="profile.material_capabilities.state",
                    capability=resolved,
                    section_state=profile.material_section_state,
                    strength=item.requirement_strength,
                    ambiguous=ambiguous,
                    hard_reason="HARD_MATERIAL_EXPLICIT_UNSUPPORTED",
                    resolution=resolution,
                )
            )
        return self._dimension(dimension, atoms)

    def _technologies(
        self,
        opportunity: PreparedOpportunityInput,
        profile: ProfileMatchingSnapshot,
    ) -> MatchDimensionResult:
        dimension = MatchDimension.TECHNOLOGY_REQUIREMENTS
        items = opportunity.technology_requirements
        boundary = self._collection_boundary(dimension, items)
        if boundary:
            return boundary
        ambiguous = len(items or []) > 1
        atoms: list[MatchAtomResult] = []
        if ambiguous:
            atoms.append(self._ambiguity(dimension, len(items or [])))
        capabilities = {
            item.technology_code: item
            for item in sorted(
                profile.technology_capabilities,
                key=lambda cap: (cap.technology_code, cap.capability_id),
            )
        }
        for index, item in enumerate(items or []):
            capability = capabilities.get(item.technology_code)
            resolution = (
                [f"technology_capability:{capability.capability_id}"]
                if capability is not None
                else ["NO_ASSERTION"]
            )
            atoms.append(
                self._state_capability_atom(
                    dimension=dimension,
                    target=item.technology_code,
                    requirement_path=f"technology_requirements[{index}]",
                    requirement_value=item.technology_code,
                    capability_path="profile.technology_capabilities.state",
                    capability=capability,
                    section_state=profile.technology_section_state,
                    strength=item.requirement_strength,
                    ambiguous=ambiguous,
                    hard_reason="HARD_TECHNOLOGY_EXPLICIT_UNSUPPORTED",
                    resolution=resolution,
                )
            )
        return self._dimension(dimension, atoms)

    def _state_capability_atom(
        self,
        *,
        dimension: MatchDimension,
        target: str,
        requirement_path: str,
        requirement_value: str | int,
        capability_path: str,
        capability: object | None,
        section_state: ProfileSectionState,
        strength: RequirementStrength,
        ambiguous: bool,
        hard_reason: str,
        resolution: Sequence[str],
    ) -> MatchAtomResult:
        capability_state = getattr(capability, "state", None)
        if capability_state == CapabilityState.SUPPORTED:
            state = AtomicMatchState.MATCH
            severity = MatchSeverity.SOFT
            reason = "CAPABILITY_EXPLICIT_SUPPORTED"
            origin = None
        elif capability_state == CapabilityState.UNSUPPORTED:
            state = AtomicMatchState.MISMATCH
            if strength == RequirementStrength.MANDATORY and not ambiguous:
                severity = MatchSeverity.HARD
                reason = hard_reason
            else:
                severity = MatchSeverity.SOFT
                reason = "CAPABILITY_EXPLICIT_UNSUPPORTED"
            origin = None
        elif capability_state == CapabilityState.UNKNOWN:
            state = AtomicMatchState.UNKNOWN
            severity = MatchSeverity.UNRESOLVED
            reason = "CAPABILITY_EXPLICIT_UNKNOWN"
            origin = UnknownOrigin.ENTERPRISE_PROFILE
        elif section_state == ProfileSectionState.CONFIRMED_COMPLETE:
            state = AtomicMatchState.MISMATCH
            severity = MatchSeverity.SOFT
            reason = "CAPABILITY_NOT_ASSERTED_COMPLETE_SECTION"
            origin = None
        else:
            state = AtomicMatchState.UNKNOWN
            severity = MatchSeverity.UNRESOLVED
            reason = "CAPABILITY_NOT_ASSERTED_INCOMPLETE_SECTION"
            origin = UnknownOrigin.ENTERPRISE_PROFILE
        return self._atom(
            dimension,
            target,
            "capability_state",
            requirement_path,
            requirement_value,
            state,
            severity,
            reason,
            origin=origin,
            capability_path=capability_path,
            capability_value=(
                capability_state.value if capability_state is not None else None
            ),
            resolution_path=resolution,
            strength=strength,
        )

    def _equipment(
        self,
        opportunity: PreparedOpportunityInput,
        profile: ProfileMatchingSnapshot,
    ) -> MatchDimensionResult:
        dimension = MatchDimension.EQUIPMENT_REQUIREMENTS
        items = opportunity.equipment_requirements
        boundary = self._collection_boundary(dimension, items)
        if boundary:
            return boundary
        atoms: list[MatchAtomResult] = []
        if len(items or []) > 1:
            atoms.append(self._ambiguity(dimension, len(items or [])))
        equipment = sorted(
            profile.equipments,
            key=lambda item: (item.equipment_type_code, item.equipment_id),
        )
        for index, item in enumerate(items or []):
            target = item.equipment_type_code
            candidates = [e for e in equipment if e.equipment_type_code == target]
            candidate_ids = [f"equipment:{e.equipment_id}" for e in candidates]
            atoms.append(
                self._atom(
                    dimension,
                    target,
                    "equipment_type_code",
                    f"equipment_requirements[{index}].equipment_type_code",
                    target,
                    AtomicMatchState.MATCH if candidates else AtomicMatchState.UNKNOWN,
                    MatchSeverity.SOFT if candidates else MatchSeverity.UNRESOLVED,
                    "EQUIPMENT_TYPE_PRESENT"
                    if candidates
                    else "PROFILE_EQUIPMENT_NOT_DECLARED",
                    origin=None if candidates else UnknownOrigin.ENTERPRISE_PROFILE,
                    capability_path="profile.equipments.equipment_type_code",
                    capability_value=target if candidates else None,
                    resolution_path=candidate_ids,
                    strength=item.requirement_strength,
                )
            )
            self._equipment_subatoms(atoms, index, item, target, candidates)
        return self._dimension(dimension, atoms)

    def _equipment_subatoms(
        self,
        atoms: list[MatchAtomResult],
        index: int,
        item,
        target: str,
        candidates: list[EquipmentSnapshot],
    ) -> None:
        base = f"equipment_requirements[{index}]"
        strength = item.requirement_strength
        if item.cnc is True:
            matching = [candidate for candidate in candidates if candidate.cnc is True]
            atoms.append(
                self._atom(
                    MatchDimension.EQUIPMENT_REQUIREMENTS,
                    target,
                    "cnc",
                    f"{base}.cnc",
                    True,
                    AtomicMatchState.MATCH if matching else AtomicMatchState.UNKNOWN,
                    MatchSeverity.SOFT if matching else MatchSeverity.UNRESOLVED,
                    "EQUIPMENT_CNC_PRESENT"
                    if matching
                    else "PROFILE_EQUIPMENT_CNC_NOT_PROVEN",
                    origin=None if matching else UnknownOrigin.ENTERPRISE_PROFILE,
                    capability_path="profile.equipments.cnc",
                    capability_value=True if matching else None,
                    resolution_path=[f"equipment:{e.equipment_id}" for e in matching],
                    strength=strength,
                )
            )
        elif item.cnc is False:
            atoms.append(
                self._atom(
                    MatchDimension.EQUIPMENT_REQUIREMENTS,
                    target,
                    "cnc",
                    f"{base}.cnc",
                    False,
                    AtomicMatchState.UNKNOWN,
                    MatchSeverity.UNRESOLVED,
                    "AMBIGUOUS_CNC_FALSE_SEMANTICS",
                    origin=UnknownOrigin.AMBIGUOUS_DOMAIN_SEMANTICS,
                    strength=strength,
                )
            )
        if item.axes is not None:
            matching = [
                candidate
                for candidate in candidates
                if candidate.axes is not None and candidate.axes >= item.axes
            ]
            atoms.append(
                self._atom(
                    MatchDimension.EQUIPMENT_REQUIREMENTS,
                    target,
                    "axes",
                    f"{base}.axes",
                    item.axes,
                    AtomicMatchState.MATCH if matching else AtomicMatchState.UNKNOWN,
                    MatchSeverity.SOFT if matching else MatchSeverity.UNRESOLVED,
                    "EQUIPMENT_AXES_SATISFIED"
                    if matching
                    else "PROFILE_EQUIPMENT_AXES_NOT_PROVEN",
                    origin=None if matching else UnknownOrigin.ENTERPRISE_PROFILE,
                    capability_path="profile.equipments.axes",
                    capability_value=max(
                        (candidate.axes or 0 for candidate in matching),
                        default=None,
                    ),
                    resolution_path=[f"equipment:{e.equipment_id}" for e in matching],
                    strength=strength,
                )
            )
        for field in (
            "working_zone_x_mm",
            "working_zone_y_mm",
            "working_zone_z_mm",
            "diameter_mm",
        ):
            value = getattr(item, field)
            if value is None:
                continue
            atoms.append(
                self._atom(
                    MatchDimension.EQUIPMENT_REQUIREMENTS,
                    target,
                    field,
                    f"{base}.{field}",
                    value,
                    AtomicMatchState.UNKNOWN,
                    MatchSeverity.UNRESOLVED,
                    "PROFILE_EQUIPMENT_UNIT_NOT_DECLARED",
                    origin=UnknownOrigin.AMBIGUOUS_DOMAIN_SEMANTICS,
                    strength=strength,
                )
            )

    def _dimensions(
        self,
        opportunity: PreparedOpportunityInput,
    ) -> MatchDimensionResult:
        dimension = MatchDimension.DIMENSIONAL_MASS_REQUIREMENTS
        items = opportunity.dimensional_mass_requirements
        boundary = self._collection_boundary(dimension, items)
        if boundary:
            return boundary
        atoms: list[MatchAtomResult] = []
        for index, item in enumerate(items or []):
            for field in ("length_mm", "width_mm", "height_mm", "diameter_mm"):
                value = getattr(item, field)
                if value is not None:
                    atoms.append(
                        self._atom(
                            dimension,
                            "dimensional_block",
                            field,
                            f"dimensional_mass_requirements[{index}].{field}",
                            value,
                            AtomicMatchState.UNKNOWN,
                            MatchSeverity.UNRESOLVED,
                            "AMBIGUOUS_DIMENSIONAL_ENVELOPE_SEMANTICS",
                            origin=UnknownOrigin.AMBIGUOUS_DOMAIN_SEMANTICS,
                            strength=item.requirement_strength,
                        )
                    )
            if item.mass_kg is not None:
                atoms.append(
                    self._atom(
                        dimension,
                        "dimensional_block",
                        "mass_kg",
                        f"dimensional_mass_requirements[{index}].mass_kg",
                        item.mass_kg,
                        AtomicMatchState.UNKNOWN,
                        MatchSeverity.UNRESOLVED,
                        "MISSING_PROFILE_CAPABILITY_MAX_WORKPIECE_MASS",
                        origin=UnknownOrigin.MISSING_PROFILE_CAPABILITY,
                        strength=item.requirement_strength,
                    )
                )
        return self._dimension(dimension, atoms)

    def _quality(
        self,
        opportunity: PreparedOpportunityInput,
        profile: ProfileMatchingSnapshot,
    ) -> MatchDimensionResult:
        dimension = MatchDimension.QUALITY_REQUIREMENTS
        items = opportunity.quality_requirements
        boundary = self._collection_boundary(dimension, items)
        if boundary:
            return boundary
        atoms: list[MatchAtomResult] = []
        quality = profile.quality_capability
        for index, item in enumerate(items or []):
            base = f"quality_requirements[{index}]"
            target = "quality_block"
            strength = item.requirement_strength
            if item.required_it_grade is not None:
                if quality is None or quality.min_it_grade is None:
                    state = AtomicMatchState.UNKNOWN
                    severity = MatchSeverity.UNRESOLVED
                    reason = "PROFILE_QUALITY_IT_GRADE_NOT_DECLARED"
                    origin = UnknownOrigin.ENTERPRISE_PROFILE
                elif quality.min_it_grade <= item.required_it_grade:
                    state = AtomicMatchState.MATCH
                    severity = MatchSeverity.SOFT
                    reason = "QUALITY_IT_GRADE_MATCH"
                    origin = None
                else:
                    state = AtomicMatchState.MISMATCH
                    severity = MatchSeverity.SOFT
                    reason = "QUALITY_IT_GRADE_MISMATCH"
                    origin = None
                atoms.append(
                    self._atom(
                        dimension,
                        target,
                        "required_it_grade",
                        f"{base}.required_it_grade",
                        item.required_it_grade,
                        state,
                        severity,
                        reason,
                        origin=origin,
                        capability_path="profile.quality_capability.min_it_grade",
                        capability_value=(quality.min_it_grade if quality else None),
                        resolution_path=(
                            [f"quality_capability:{quality.capability_id}"]
                            if quality
                            else []
                        ),
                        strength=strength,
                    )
                )
            if item.maximum_ra_um is not None:
                atoms.append(
                    self._atom(
                        dimension,
                        target,
                        "maximum_ra_um",
                        f"{base}.maximum_ra_um",
                        item.maximum_ra_um,
                        AtomicMatchState.UNKNOWN,
                        MatchSeverity.UNRESOLVED,
                        "PROFILE_QUALITY_UNIT_NOT_DECLARED",
                        origin=UnknownOrigin.AMBIGUOUS_DOMAIN_SEMANTICS,
                        capability_path="profile.quality_capability.min_ra",
                        capability_value=(quality.min_ra if quality else None),
                        strength=strength,
                    )
                )
            if item.measuring_capability_required is not None:
                if item.measuring_capability_required is False:
                    state = AtomicMatchState.NOT_APPLICABLE
                    severity = MatchSeverity.NOT_APPLICABLE
                    reason = "QUALITY_MEASURING_CAPABILITY_NOT_REQUIRED"
                    origin = None
                elif quality is not None and quality.measuring_tools is True:
                    state = AtomicMatchState.MATCH
                    severity = MatchSeverity.SOFT
                    reason = "QUALITY_MEASURING_CAPABILITY_PRESENT"
                    origin = None
                else:
                    state = AtomicMatchState.UNKNOWN
                    severity = MatchSeverity.UNRESOLVED
                    reason = "PROFILE_QUALITY_MEASURING_CAPABILITY_NOT_PROVEN"
                    origin = UnknownOrigin.ENTERPRISE_PROFILE
                atoms.append(
                    self._atom(
                        dimension,
                        target,
                        "measuring_capability_required",
                        f"{base}.measuring_capability_required",
                        item.measuring_capability_required,
                        state,
                        severity,
                        reason,
                        origin=origin,
                        capability_path="profile.quality_capability.measuring_tools",
                        capability_value=(quality.measuring_tools if quality else None),
                        strength=strength,
                    )
                )
            if item.cmm_required is not None:
                atoms.append(
                    self._atom(
                        dimension,
                        target,
                        "cmm_required",
                        f"{base}.cmm_required",
                        item.cmm_required,
                        AtomicMatchState.UNKNOWN,
                        MatchSeverity.UNRESOLVED,
                        "AMBIGUOUS_CMM_CAPABILITY_MAPPING",
                        origin=UnknownOrigin.AMBIGUOUS_DOMAIN_SEMANTICS,
                        capability_path="profile.quality_capability.cim_machine",
                        capability_value=(quality.cim_machine if quality else None),
                        strength=strength,
                    )
                )
        return self._dimension(dimension, atoms)

    def _certificates(
        self,
        opportunity: PreparedOpportunityInput,
        profile: ProfileMatchingSnapshot,
        evaluation_date: date,
    ) -> MatchDimensionResult:
        dimension = MatchDimension.REQUIRED_CERTIFICATES
        items = opportunity.required_certificates
        boundary = self._collection_boundary(dimension, items)
        if boundary:
            return boundary
        atoms: list[MatchAtomResult] = []
        if len(items or []) > 1:
            atoms.append(self._ambiguity(dimension, len(items or [])))
        certificates = sorted(
            profile.certificates,
            key=lambda item: (
                item.certificate_type_code,
                item.issue_date,
                item.expiry_date,
                item.certificate_id,
            ),
        )
        for index, item in enumerate(items or []):
            base = f"required_certificates[{index}]"
            matches = [
                certificate
                for certificate in certificates
                if certificate.certificate_type_code == item.certificate_type_code
                and certificate.issue_date <= evaluation_date <= certificate.expiry_date
            ]
            atoms.append(
                self._atom(
                    dimension,
                    item.certificate_type_code,
                    "certificate_type_currently_valid",
                    f"{base}.certificate_type_code",
                    item.certificate_type_code,
                    AtomicMatchState.MATCH if matches else AtomicMatchState.UNKNOWN,
                    MatchSeverity.SOFT if matches else MatchSeverity.UNRESOLVED,
                    "CERTIFICATE_TYPE_CURRENTLY_VALID"
                    if matches
                    else "PROFILE_CURRENT_CERTIFICATE_NOT_PROVEN",
                    origin=None if matches else UnknownOrigin.ENTERPRISE_PROFILE,
                    capability_path="profile.certificates.certificate_type_code",
                    capability_value=(item.certificate_type_code if matches else None),
                    resolution_path=[
                        f"certificate:{certificate.certificate_id}"
                        for certificate in matches
                    ],
                    strength=item.requirement_strength,
                )
            )
            for field, reason in (
                ("required_by", "AMBIGUOUS_CERTIFICATE_REQUIRED_BY_SEMANTICS"),
                (
                    "valid_through",
                    "AMBIGUOUS_CERTIFICATE_VALID_THROUGH_SEMANTICS",
                ),
            ):
                value = getattr(item, field)
                if value is not None:
                    atoms.append(
                        self._atom(
                            dimension,
                            item.certificate_type_code,
                            field,
                            f"{base}.{field}",
                            value,
                            AtomicMatchState.UNKNOWN,
                            MatchSeverity.UNRESOLVED,
                            reason,
                            origin=UnknownOrigin.AMBIGUOUS_DOMAIN_SEMANTICS,
                            strength=item.requirement_strength,
                        )
                    )
        return self._dimension(dimension, atoms)
