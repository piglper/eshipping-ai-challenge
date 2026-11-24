"""Schema of the synthetic data specification (data_sample/spec/*.yaml)."""

from datetime import date
from pathlib import Path
from typing import Self

import yaml
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from eshipping_ai.domain.vocabulary import EventClassifier, MailClass, VerdictCode


class SpecModel(BaseModel):
    """Base of the specification models: unknown keys are an error."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Party(SpecModel):
    """Someone who sends or receives mails."""

    name: str
    address: str
    signature: str = ""


class SpecMail(SpecModel):
    """One mail of a shipment thread, or a noise mail."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str = Field(pattern=r"^[A-Z]\d+$")
    sender: str = Field(alias="from")
    to: str
    date: AwareDatetime
    subject: str
    classes: tuple[MailClass, ...] = Field(min_length=1)
    body: str
    quote: str | None = None


class GoldField(SpecModel):
    """Expected value of one shipment field and its verdict against the ERP."""

    value: object
    verdict: VerdictCode
    source: str | None
    known_at: date | None = None
    classifier: EventClassifier | None = None
    erp: str | None = None
    note: str | None = None


class SpecShipment(SpecModel):
    """A synthetic shipment: its ERP row, its mails and the expected result."""

    operation: str = Field(pattern=r"^ES\d{8}$")
    erp: dict[str, str]
    mails: tuple[SpecMail, ...] = Field(min_length=1)
    gold: dict[str, GoldField]

    @model_validator(mode="after")
    def _check_references(self) -> Self:
        ids = [mail.id for mail in self.mails]
        if len(set(ids)) != len(ids):
            msg = f"{self.operation}: repeated mail ids"
            raise ValueError(msg)
        for position, mail in enumerate(self.mails):
            if mail.quote is not None and mail.quote not in ids[:position]:
                msg = f"{self.operation}/{mail.id}: quotes {mail.quote}, not an earlier mail"
                raise ValueError(msg)
        for field, expected in self.gold.items():
            if expected.source is not None and expected.source not in ids:
                msg = f"{self.operation}/{field}: unknown source {expected.source}"
                raise ValueError(msg)
        return self


class ErpSpec(SpecModel):
    """How the synthetic ERP read is stamped."""

    read_at: AwareDatetime


class Spec(SpecModel):
    """The whole synthetic data set."""

    version: int
    mailbox: str
    erp: ErpSpec
    parties: dict[str, Party]
    shipments: tuple[SpecShipment, ...] = Field(min_length=1)
    noise: tuple[SpecMail, ...] = ()

    @model_validator(mode="after")
    def _check_parties_and_columns(self) -> Self:
        mails = [mail for shipment in self.shipments for mail in shipment.mails]
        for mail in [*mails, *self.noise]:
            for party in (mail.sender, mail.to):
                if party not in self.parties:
                    msg = f"mail {mail.id}: unknown party {party!r}"
                    raise ValueError(msg)
        columns = list(self.shipments[0].erp)
        for shipment in self.shipments:
            if list(shipment.erp) != columns:
                msg = f"{shipment.operation}: ERP columns differ from the first shipment"
                raise ValueError(msg)
        return self


def load_spec(path: Path) -> Spec:
    """Read and validate a specification file.

    Args:
        path: YAML file.

    Returns:
        The validated specification.
    """
    return Spec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
