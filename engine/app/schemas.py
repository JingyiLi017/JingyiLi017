from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .defaults import DEFAULT_LLM_MODEL, DEFAULT_TENSION_STYLE, DEFAULT_TENSION_TARGETS


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class BookCreateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    author: str | None = None
    language: str = "zh"
    notes: str | None = None

    @model_validator(mode="after")
    def ensure_title_or_name(self) -> "BookCreateRequest":
        value = (self.title or self.name or "").strip()
        if not value:
            raise ValueError("title_or_name_required")
        self.title = value
        self.name = value
        return self


class BookItem(BaseModel):
    book_id: UUID
    profile_id: UUID | None = None
    title: str
    author: str | None
    language: str
    notes: str | None
    created_at: datetime


class BookListResponse(BaseModel):
    items: list[BookItem]


class ChapterCreateRequest(BaseModel):
    chapter_no: int = Field(ge=1)
    title: str = Field(default="", max_length=300)
    arc_id: str | None = None
    arc_index: int | None = Field(default=None, ge=1)


class ChapterItem(BaseModel):
    chapter_id: UUID
    book_id: UUID
    chapter_no: int
    title: str
    arc_id: str | None = None
    arc_index: int | None = None
    created_at: datetime


class JobCreateRequest(BaseModel):
    capability_id: str
    input: dict[str, Any]
    client_context: dict[str, Any] | None = None


class JobProgress(BaseModel):
    pct: int = Field(ge=0, le=100)
    phase: str
    message: str | None = None
    counters: dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    job_id: UUID
    capability_id: str
    status: Literal["queued", "running", "succeeded", "failed", "canceled"]
    progress: JobProgress
    run_id: UUID | None = None
    error: ErrorDetail | None = None
    created_at: datetime
    updated_at: datetime


class SubmitJobResponse(BaseModel):
    job_id: UUID
    status: Literal["queued", "running"]
    queued_at: datetime
    request_id: str


class SearchItem(BaseModel):
    chunk_id: UUID
    score: float
    chapter_id: UUID
    chapter_order: int | None = None
    snippet: str


class SearchResponse(BaseModel):
    query: str
    items: list[SearchItem]


class SkillRunCreateRequest(BaseModel):
    book_id: UUID
    skill_name: str
    schema_ver: int = 1
    output: dict[str, Any]


class SkillRunCreateResponse(BaseModel):
    skill_run_id: UUID
    book_id: UUID
    skill_name: str
    schema_ver: int
    output: dict[str, Any]
    created_at: datetime


class LedgerApplyRequest(BaseModel):
    skill_run_id: UUID
    apply_policy: dict[str, Literal["upsert_safe", "append_only", "merge_by_key_needs_review"]]


class LedgerApplyResponse(BaseModel):
    ok: bool
    applied: dict[str, int]
    needs_review: dict[str, int]
    apply_policy: dict[str, str]


class ProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    note: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    dos: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)


class ProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = None
    features: dict[str, Any] | None = None
    dos: list[str] | None = None
    donts: list[str] | None = None


class BookProfileBindRequest(BaseModel):
    profile_id: UUID | None = None


class ProfileFromSplitbookRequest(BaseModel):
    splitbook_id: UUID
    name: str = Field(min_length=1, max_length=200)
    mode: Literal["create", "merge"] = "create"


class ProfileLearnFromTextsRequest(BaseModel):
    profile_id: UUID
    book_id: UUID | None = None
    text_ver_ids: list[UUID] = Field(default_factory=list)
    mode: Literal["merge", "replace"] = "merge"
    note: str | None = None


class ProfileSetActiveVersionRequest(BaseModel):
    version: int = Field(ge=1)
    note: str | None = None


class ProfileDiffRequest(BaseModel):
    from_version: int = Field(alias="from", ge=1)
    to_version: int = Field(alias="to", ge=1)
    mode: str | None = "leaf"


class ProfileCloneRequest(BaseModel):
    new_name: str = Field(min_length=1, max_length=200)
    note: str | None = None


class BookProfileLinkRequest(BaseModel):
    profile_id: UUID
    role: Literal["main", "experiment"] = "experiment"


class SplitbookCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    author: str | None = None
    source_path: str | None = None
    note: str | None = None


class SplitbookAllowGuardRequest(BaseModel):
    allow_guard: bool


class ProfileItem(BaseModel):
    profile_id: UUID
    name: str
    note: str | None = None
    active_version: int | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    dos: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None


class ProfileListResponse(BaseModel):
    items: list[ProfileItem]


class TemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    level: Literal["volume", "arc", "chapter", "scene"]
    tags: list[str] = Field(default_factory=list)
    schema_ver: int = 1
    graph: dict[str, Any]
    meta: dict[str, Any] = Field(default_factory=dict)
    source_book_id: UUID | None = None
    source_chunk_ids: list[UUID] = Field(default_factory=list)
    source_note: str | None = None


class TemplateItem(BaseModel):
    template_id: UUID
    profile_id: UUID
    name: str
    level: str
    tags: list[str]
    schema_ver: int
    graph: dict[str, Any]
    meta: dict[str, Any]
    created_at: datetime


class TemplateListResponse(BaseModel):
    items: list[TemplateItem]


class TemplateRecommendRequest(BaseModel):
    profile_id: UUID
    level: Literal["volume", "arc", "chapter", "scene"] | None = None
    top_k: int = Field(default=5, ge=1, le=30)


class TemplateUseRequest(BaseModel):
    book_id: UUID | None = None
    chapter_id: UUID | None = None
    usage_type: Literal["outline", "detail", "draft"]
    feedback: dict[str, Any] = Field(default_factory=dict)


class TemplateUseResponse(BaseModel):
    usage_id: UUID
    template_id: UUID
    book_id: UUID | None = None
    chapter_id: UUID | None = None
    usage_type: str
    feedback: dict[str, Any]
    created_at: datetime


class StructureBeatsExtractRequest(BaseModel):
    scope: dict[str, list[int]] = Field(default_factory=lambda: {"chapter_range": [1, 50]})
    schema_ver: int = 1
    llm_model: str | None = None


class GenerateTemplateFromBeatsRequest(BaseModel):
    skill_run_id: UUID
    level: Literal["volume", "arc", "chapter", "scene"] = "chapter"
    name: str = Field(min_length=1, max_length=200)
    tags: list[str] = Field(default_factory=list)


class TensionEvalRequest(BaseModel):
    profile_id: UUID | None = None
    chapter_version_id: UUID | None = None
    input_mode: Literal["outline", "draft"] = "draft"
    llm_model: str = DEFAULT_LLM_MODEL
    targets: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_TENSION_TARGETS))
    schema_ver: int = 1


class TensionApplyRequest(BaseModel):
    skill_run_id: UUID
    apply_target: Literal["outline_detail"] = "outline_detail"
    mode: Literal["staging_then_apply"] = "staging_then_apply"
    selected_patch_ids: list[str] | None = None


class TensionControlTargets(BaseModel):
    conflict_strength: float = Field(default=DEFAULT_TENSION_TARGETS["conflict_strength"], ge=0.0, le=1.0)
    stakes: float = Field(default=DEFAULT_TENSION_TARGETS["stakes"], ge=0.0, le=1.0)
    cost: float = Field(default=DEFAULT_TENSION_TARGETS["cost"], ge=0.0, le=1.0)
    pace: float = Field(default=DEFAULT_TENSION_TARGETS["pace"], ge=0.0, le=1.0)
    reversal: float = Field(default=DEFAULT_TENSION_TARGETS["reversal"], ge=0.0, le=1.0)
    hook: float = Field(default=DEFAULT_TENSION_TARGETS["hook"], ge=0.0, le=1.0)


class TensionControlStyle(BaseModel):
    face_slap_density: float = Field(default=DEFAULT_TENSION_STYLE["face_slap_density"], ge=0.0, le=1.0)
    upgrade_density: float = Field(default=DEFAULT_TENSION_STYLE["upgrade_density"], ge=0.0, le=1.0)


class TensionControlPlanRequest(BaseModel):
    profile_id: UUID | None = None
    outline_id: UUID | None = None
    targets: TensionControlTargets = Field(default_factory=TensionControlTargets)
    style: TensionControlStyle = Field(default_factory=TensionControlStyle)
    llm_model: str = DEFAULT_LLM_MODEL
    schema_ver: int = 1


class MechanicsPreviewRequest(BaseModel):
    outline_id: UUID | None = None
    mechanic: Literal[
        "face_slap",
        "upgrade",
        "reversal",
        "timer",
        "raise_stakes",
        "cost_hardening",
        "rescue",
        "betrayal",
        "micro_cost",
        "micro_obstacle",
        "strengthen_obstacle",
    ]
    selected_node_id: str | None = None
    strength: float = Field(default=0.7, ge=0.0, le=1.0)


class SimilarityGuardRequest(BaseModel):
    book_id: UUID | None = None
    chapter_version_id: UUID
    embedding_model: str | None = None
    vec_high: float = Field(default=0.86, ge=0.0, le=1.0)
    vec_mid: float = Field(default=0.80, ge=0.0, le=1.0)
    ngram_high: float = Field(default=0.20, ge=0.0, le=1.0)
    ngram_mid: float = Field(default=0.12, ge=0.0, le=1.0)
    schema_ver: int = 1


class SimilarityGuardTextRequest(BaseModel):
    text_ver_id: UUID | None = None
    scope: list[Literal["material_card", "splitbook_chunk"]] = Field(default_factory=lambda: ["material_card", "splitbook_chunk"])
    sim_threshold: float = Field(default=0.86, ge=0.0, le=1.0)
    top_k: int = Field(default=5, ge=1, le=20)
    embedding_model: str | None = None


class OutlineDetailConflict(BaseModel):
    goal_clarity: float = 0.0
    opposition_strength: float = 0.0
    stake_level: float = 0.0
    cost_level: float = 0.0
    time_pressure: float = 0.0
    info_gap: float = 0.0
    reversal_power: float = 0.0


class OutlineDetailNode(BaseModel):
    model_config = {"populate_by_name": True}
    node_id: str
    type: Literal[
        "hook",
        "goal",
        "obstacle",
        "escalation",
        "turning_point",
        "cost",
        "gain",
        "cliffhanger",
        "micro_obstacle",
        "micro_cost",
        "micro_timer",
        "micro_info_gap",
        "micro_turning_point",
        "micro_stake_raise",
        "micro_rescue",
        "micro_betrayal",
        "micro_revelation",
        "micro_chase",
        "micro_gamble",
        "micro_upgrade",
    ]
    summary: str
    beats: list[str] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    world_facts: list[str] = Field(default_factory=list)
    plot_hooks: list[str] = Field(default_factory=list)
    conflict: OutlineDetailConflict = Field(default_factory=OutlineDetailConflict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict, alias="_meta")


class OutlineDetailV1(BaseModel):
    schema_name: Literal["OUTLINE_DETAIL"] = "OUTLINE_DETAIL"
    schema_ver: int = 1
    chapter_no: int
    chapter_title: str
    template_ref: dict[str, Any] = Field(default_factory=dict)
    nodes: list[OutlineDetailNode] = Field(default_factory=list)
    global_constraints: dict[str, Any] = Field(default_factory=dict)


class OutlineDetailSaveRequest(BaseModel):
    outline: dict[str, Any]
    note: str | None = None


class OutlinePatchApplyRequest(BaseModel):
    plan_skill_run_id: UUID | None = None
    skill_run_id: UUID | None = None
    selected_patch_ids: list[str] = Field(default_factory=list)
    targets: TensionControlTargets = Field(default_factory=TensionControlTargets)
    style: TensionControlStyle = Field(default_factory=TensionControlStyle)
    auto_eval: bool = True


class BookTensionRepairPlanRequest(BaseModel):
    chapter_from: int | None = Field(default=None, ge=1)
    chapter_to: int | None = Field(default=None, ge=1)
    targets: TensionControlTargets = Field(default_factory=TensionControlTargets)
    style: TensionControlStyle = Field(default_factory=TensionControlStyle)
    actions_override: list[dict[str, Any]] = Field(default_factory=list)
    actions_override_by_chapter: list[dict[str, Any]] = Field(default_factory=list)


class ArcTargetWeights(BaseModel):
    overall: float = Field(default=0.6, ge=0.0, le=1.0)
    cost: float = Field(default=0.2, ge=0.0, le=1.0)
    reversal: float = Field(default=0.2, ge=0.0, le=1.0)


class ArcTargetUpsertRequest(BaseModel):
    arc_id: str = Field(min_length=1, max_length=100)
    target_shape: Literal["ramp", "late_peak", "early_peak", "plateau", "sawtooth"]
    target_points: list[float] = Field(min_length=5, max_length=5)
    weights: ArcTargetWeights = Field(default_factory=ArcTargetWeights)


class ArcTargetItem(BaseModel):
    book_id: UUID
    arc_id: str
    target_shape: str
    target_points: list[float]
    weights: dict[str, float]
    created_at: datetime
    updated_at: datetime


class ArcTargetListResponse(BaseModel):
    items: list[ArcTargetItem]


class TemplateEvolveRequest(BaseModel):
    book_id: UUID | None = None
    min_samples: int = Field(default=8, ge=1, le=1000)
    min_mean_overall: float = Field(default=0.05, ge=0.0, le=1.0)
    scope: dict[str, Any] = Field(default_factory=dict)


class TemplateVariantItem(BaseModel):
    variant_id: UUID
    base_template_id: UUID | None = None
    unique_key: str | None = None
    name: str
    scope: dict[str, Any]
    recipe: dict[str, Any]
    enabled: bool
    weight: float
    stats: dict[str, Any]
    created_at: datetime


class TemplateVariantListResponse(BaseModel):
    items: list[TemplateVariantItem]


class RepairEffectSampleCreateRequest(BaseModel):
    book_id: UUID
    arc_id: str | None = None
    chapter_no: int = Field(ge=1)
    before_eval_run_id: UUID
    after_eval_run_id: UUID
    applied_mechanics: list[str] = Field(default_factory=list)
    delta: dict[str, float] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class ChapterRevisionReportRequest(BaseModel):
    book_id: UUID
    chapter_id: UUID
    from_version: int = Field(ge=1)
    to_version: int = Field(ge=1)
    before_eval_run_id: UUID
    after_eval_run_id: UUID
    include_similarity_guard: bool = True


class MaterialCardCreateRequest(BaseModel):
    book_id: UUID | None = None
    source_type: str = "manual"
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    tag: str | None = None
    importance: int = Field(default=3, ge=1, le=5)


class MaterialCardItem(BaseModel):
    card_id: UUID
    book_id: UUID | None = None
    source_type: str
    title: str
    content: str
    tag: str | None = None
    importance: int
    created_at: datetime
    score: float | None = None


class MaterialCardListResponse(BaseModel):
    items: list[MaterialCardItem]


class MaterialKnnRequest(BaseModel):
    query_text: str = Field(min_length=1)
    k: int = Field(default=20, ge=1, le=100)
    book_id: UUID | None = None
    tag: str | None = None


class MaterialImportFromChunksRequest(BaseModel):
    book_id: UUID
    source_id: UUID | None = None
    tag: str | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    source_type: str = "splitbook"
    importance: int = Field(default=3, ge=1, le=5)
    auto_embed: bool = True


class RefInboxFromMaterialRequest(BaseModel):
    card_id: UUID
    context: dict[str, Any] = Field(default_factory=dict)


class RefInboxStatusRequest(BaseModel):
    status: Literal["new", "used", "archived"]


class DraftCommitWriteback(BaseModel):
    update_outline: bool = True
    extract_facts: bool = True
    extract_growth: bool = True
    extract_timeline: bool = True
    extract_new_materials: bool = True
    run_eval: bool = True


class DraftCommitRequest(BaseModel):
    text_ver_id: UUID | None = None
    text_content: str | None = None
    outline_version: int | None = None
    writeback: DraftCommitWriteback = Field(default_factory=DraftCommitWriteback)


class RefInboxFromTemplateRequest(BaseModel):
    asset_id: UUID
    note: str | None = None
