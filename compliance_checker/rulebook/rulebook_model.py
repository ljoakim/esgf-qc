from __future__ import annotations

import enum
import typing

import pydantic


class ERuleListLogic(enum.Enum):
    ALL = "all"
    EXACTLY_ONE = "exactly one"
    AT_LEAST_ONE = "at least one"
    NONE = "none"


class EByteOrder(enum.Enum):
    NATIVE = "="
    LITTLE_ENDIAN = "<"
    BIG_ENDIAN = ">"


class EMonotonicity(enum.Enum):
    INCREASING = "<="
    STRICTLY_INCREASING = "<"
    DECREASING = ">="
    STRICTLY_DECREASING = ">"


class ECompressionType(enum.Enum):
    ANY = "ANY"
    NONE = None
    ZLIB = "zlib"
    SZIP = "szip"
    ZSTD = "zstd"
    BZIP2 = "bzip2"
    BLOSC = "blosc"


class EAxis(enum.Enum):
    T = "T"
    Z = "Z"
    Y = "Y"
    X = "X"


class LUCF(pydantic.BaseModel):
    axis: list[EAxis] = pydantic.Field(default_factory=list)


class LUCMIPTime(pydantic.BaseModel):
    range: str | Lookup
    frequency: str | Lookup
    variable: str | Lookup


class LUCMIP(pydantic.BaseModel):
    path_drs: str = ""
    file_drs: str = ""
    time: LUCMIPTime | None = None


class LookupTable(pydantic.BaseModel):
    cv: dict[str, list[str]] | None = None
    cf: LUCF | None = None
    cmip: LUCMIP | None = None


class Lookup(pydantic.BaseModel):
    lookup: str


class RuleBaseModel(pydantic.BaseModel):
    description: str = ""


class FileFormatRule(RuleBaseModel):
    data_model: str


class DimensionRule(RuleBaseModel):
    dimension: str | Lookup | list[str | Lookup]
    required: bool = True
    size: int = 0


class AttributeRule(RuleBaseModel):
    attribute: str | Lookup | list[str | Lookup]
    required: bool = True
    must_equal: str | float | Lookup | None = None
    allowed_values: Lookup | list[str | float | Lookup] | None = None
    pattern: str | None = None

    @pydantic.model_validator(mode="before")
    @classmethod
    def check_mutually_exclusive_conditions(cls, data: typing.Any) -> typing.Any:
        if isinstance(data, dict):
            mutually_exclusive_conditions = {"must_equal", "allowed_values", "pattern"}
            if len(mutually_exclusive_conditions.intersection(data.keys())) > 1:
                raise AssertionError("Specified conditions are mutually exclusive.")
        return data


class VariableRule(RuleBaseModel):
    variable: str | Lookup | list[str | Lookup]
    required: bool = True
    dimensions: list[str | Lookup] | None = None
    compression_type: ECompressionType = ECompressionType.ANY
    compression_level: int | None = None
    rules: RuleUnion | RuleUnionList = pydantic.Field(default_factory=list)


class DataRule(RuleBaseModel):
    dtype: str
    byteorder: EByteOrder = EByteOrder.NATIVE
    monotonicity: EMonotonicity | None = None
    shape: list[int | Lookup] | None = None
    min: float | None = None
    max: float | None = None


class ConditionalRule(RuleBaseModel):
    condition: RuleUnion | RuleUnionList = pydantic.Field(..., validation_alias=pydantic.AliasChoices("condition", "if"))
    dependent: RuleUnion | RuleUnionList = pydantic.Field(..., validation_alias=pydantic.AliasChoices("dependent", "then"))


class RuleListLogicRule(RuleBaseModel):
    logic: ERuleListLogic = ERuleListLogic.ALL
    rules: RuleUnion | RuleUnionList


class RuleSection(pydantic.BaseModel):
    section: str = pydantic.Field(pattern=r"^[0-9]+(\.[0-9]+)*$")
    heading: str
    rules: RuleUnion | RuleUnionList


class RuleBookModel(pydantic.BaseModel):
    rulebook: str
    lookup_table: LookupTable | None = None
    rule_sections: list[RuleSection] | None = None


RuleUnion = FileFormatRule | DimensionRule | AttributeRule | VariableRule | DataRule | ConditionalRule | RuleListLogicRule
RuleUnionList = list[RuleUnion]
