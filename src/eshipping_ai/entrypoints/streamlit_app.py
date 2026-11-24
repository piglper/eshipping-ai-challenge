"""Operators' view of the PoC (ADR-0004, docs/10_diseno_poc.md §5.2), reduced scope.

Three tabs: the discrepancies of every shipment by priority, the view of one shipment (its
fields and the timeline of what each source said, with quotes), and a simple correction
(accept, correct or reject a value), after which the shipment is reconciled again.

It works on the same directory as the CLI. Run it with ``make ui``; the options come from
the environment: ``ESHIPPING_WORKDIR`` (``data/output`` by default), ``ESHIPPING_ERP``
(the ERP export, needed to reconcile after a correction), ``ESHIPPING_NOW`` (fixed clock,
ISO with zone) and ``ESHIPPING_TZ``.
"""

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
from sqlalchemy import create_engine

from eshipping_ai.adapters.clock import FixedClock, SystemClock
from eshipping_ai.adapters.config_yaml import load_reconciliation_config
from eshipping_ai.adapters.erp_csv import CsvErpGateway
from eshipping_ai.adapters.log_notifier import LogNotifier
from eshipping_ai.adapters.sql_repository import SqlRepository, create_schema
from eshipping_ai.application.reconcile import ReconcileShipments
from eshipping_ai.application.report import shipment_report
from eshipping_ai.application.review import ApplyCorrection, Decision, ReviewError
from eshipping_ai.domain.policy import ReconciliationConfig
from eshipping_ai.domain.ports import Clock
from eshipping_ai.domain.vocabulary import CorrectionAction, EventClassifier

_ACTIONS = {
    "Aceptar el valor": CorrectionAction.ACCEPT,
    "Corregir el valor": CorrectionAction.CORRECT,
    "Rechazar el valor": CorrectionAction.REJECT,
}


@st.cache_resource
def _repository(workdir: str) -> SqlRepository:
    path = Path(workdir)
    path.mkdir(parents=True, exist_ok=True)
    url = os.environ.get("ESHIPPING_DATABASE_URL") or f"sqlite:///{path / 'eshipping.db'}"
    engine = create_engine(url)
    create_schema(engine)
    return SqlRepository(engine)


def _clock() -> Clock:
    now = os.environ.get("ESHIPPING_NOW")
    return FixedClock(datetime.fromisoformat(now)) if now else SystemClock()


def _discrepancies(repo: SqlRepository) -> None:
    rows = [
        {
            "Prioridad": line.priority or "",
            "Expediente": report.shipment_id,
            "Campo": line.field,
            "Veredicto": line.verdict,
            "Correos": line.mail_value,
            "ERP": line.erp_value,
            "Regla": line.rule,
            "Evidencia": line.evidence,
        }
        for report in (shipment_report(s, repo, repo) for s in repo.shipment_ids())
        for line in report.lines
        if line.verdict and line.verdict != "MATCH"
    ]
    rows.sort(key=lambda row: (row["Prioridad"] or "P9", row["Expediente"], row["Campo"]))
    st.metric("Discrepancias abiertas", len(rows))
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info("No hay discrepancias. Procesa correos con `eshipping run`.")


def _shipment(repo: SqlRepository, shipment_id: str) -> None:
    report = shipment_report(shipment_id, repo, repo)
    st.subheader("Campos")
    st.dataframe(
        [
            {
                "Prioridad": line.priority or "",
                "Campo": line.field,
                "Correos": line.mail_value,
                "ERP": line.erp_value,
                "Veredicto": line.verdict,
                "Regla": line.rule,
                "Conflicto": "sí" if line.in_conflict else "",
                "Fuente": line.source_role,
            }
            for line in report.lines
            if line.mail_value is not None or line.verdict is not None
        ],
        hide_index=True,
        use_container_width=True,
    )
    st.subheader("Línea temporal")
    observations = sorted(repo.observations_for(shipment_id), key=lambda o: o.known_at)
    st.dataframe(
        [
            {
                "Conocido": o.known_at.isoformat(timespec="minutes"),
                "Campo": o.field,
                "Valor": o.value,
                "Estado": o.classifier.value,
                "Fuente": f"{o.source_role.value} ({o.source_rank.value})",
                "Escalón": o.provenance.tier.value,
                "Zona": o.zone.value,
                "Vigente": "sí" if o.status.value == "active" else o.status.value,
                "Cita": o.evidence.text,
            }
            for o in observations
        ],
        hide_index=True,
        use_container_width=True,
    )


def _correction(
    repo: SqlRepository, shipment_id: str, config: ReconciliationConfig, tz: ZoneInfo
) -> None:
    erp = os.environ.get("ESHIPPING_ERP")
    with st.form("correction"):
        field = st.selectbox("Campo", list(config.fields))
        label = st.radio("Decisión", list(_ACTIONS))
        value = st.text_input("Valor nuevo (fechas como AAAA-MM-DD)")
        state = st.selectbox("Estado de una fecha", [c.value for c in EventClassifier], index=1)
        reason = st.text_input("Motivo")
        user = st.text_input("Usuario", value="operador")
        submitted = st.form_submit_button("Guardar")
    if not submitted:
        return
    decision = Decision(
        shipment_id=shipment_id,
        field=str(field),
        action=_ACTIONS[str(label)],
        user_id=user,
        value=value or None,
        reason=reason or None,
        classifier=EventClassifier(state),
    )
    clock = _clock()
    try:
        correction = ApplyCorrection(repo, repo, clock, config, tz).apply(decision)
    except ReviewError as error:
        st.error(str(error))
        return
    if erp:
        gateway = CsvErpGateway(Path(erp), clock.now() if os.environ.get("ESHIPPING_NOW") else None)
        ReconcileShipments(gateway, repo, repo, repo, LogNotifier(), clock, config).run(
            {shipment_id: shipment_id}
        )
        notice = ("success", f"Guardado ({correction.correction_id}) y expediente reconciliado.")
    else:
        notice = (
            "warning",
            f"Guardado ({correction.correction_id}). Define ESHIPPING_ERP para reconciliar.",
        )
    # Draw the page again so that the list and the timeline show the decision.
    st.session_state["notice"] = notice
    st.rerun()


def main() -> None:
    """Draw the page."""
    st.set_page_config(page_title="EShipping · expedientes", layout="wide")
    st.title("Expedientes y discrepancias")
    workdir = os.environ.get("ESHIPPING_WORKDIR", "data/output")
    config = load_reconciliation_config(
        Path(os.environ.get("ESHIPPING_CONFIG", "config")) / "reconciliation.yaml"
    )
    tz = ZoneInfo(os.environ.get("ESHIPPING_TZ", "Europe/Madrid"))
    repo = _repository(workdir)
    shipments = list(repo.shipment_ids())
    st.caption(
        f"Datos de {workdir}: {len(shipments)} expedientes. El sistema no escribe en el ERP."
    )
    notice = st.session_state.pop("notice", None)
    if notice:
        kind, text = notice
        (st.success if kind == "success" else st.warning)(text)
    tab_list, tab_shipment, tab_review = st.tabs(["Discrepancias", "Expediente", "Corrección"])
    with tab_list:
        _discrepancies(repo)
    if not shipments:
        return
    shipment_id = st.sidebar.selectbox("Expediente", shipments)
    with tab_shipment:
        _shipment(repo, str(shipment_id))
    with tab_review:
        _correction(repo, str(shipment_id), config, tz)


main()
