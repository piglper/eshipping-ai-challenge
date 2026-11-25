"""Presentation of an evaluation: Markdown for people and JSON for tools.

Both hold aggregated counts only, so that the report of a confidential gold can be shared.
The mismatches name shipments and are written only when asked for (``--verbose``).
"""

from collections import Counter
from collections.abc import Mapping
from typing import Any

from eshipping_ai.application.evaluate import (
    EXTRACTED_WRONG,
    NOT_CHOSEN,
    NOT_EXTRACTED,
    SPURIOUS,
    UNRESOLVED,
    EvaluationReport,
    Proportion,
    Score,
    total_score,
)

_ASSOCIATION_LABELS = {
    "auto_right": "Automática y correcta",
    "auto_wrong": "Automática y equivocada",
    "review": "A revisión (con el expediente correcto entre los candidatos)",
    "missing": "Sin asociar",
    "noise_right": "Ruido sin asociar (correcto)",
    "noise_wrong": "Ruido asociado a un expediente",
}


_STAGES = {
    "right": "Acierto",
    NOT_EXTRACTED: "No extraído",
    EXTRACTED_WRONG: "Extraído mal",
    NOT_CHOSEN: "Leído, no elegido",
    SPURIOUS: "De más",
}
_TIER_LABELS = {
    "rule": "Reglas",
    "template": "Plantilla",
    "ml": "ML",
    "llm": "LLM",
    "human": "Persona",
    UNRESOLVED: "Sin resolver (a una persona)",
}
_ZONE_LABELS = {"auto": "automática", "review": "revisión", "not_proposed": "no propuesto"}


def _pct(value: float) -> str:
    return f"{value * 100:.1f} %".replace(".", ",")


def _interval(bounds: tuple[float, float]) -> str:
    low, high = bounds
    return f"[{_pct(low)} - {_pct(high)}]"


def _proportion(p: Proportion) -> str:
    if not p.total:
        return "—"
    return f"{p.right}/{p.total} = {_pct(p.rate)} {_interval(p.interval)}"


def _score_cells(s: Score) -> str:
    precision = f"{_pct(s.precision)} {_interval(s.precision_interval)}" if s.tp + s.fp else "—"
    recall = f"{_pct(s.recall)} {_interval(s.recall_interval)}" if s.tp + s.fn else "—"
    f1 = _pct(s.f1) if s.tp + s.fp and s.tp + s.fn else "—"
    return f"{s.tp + s.fn} | {s.tp + s.fp} | {s.tp} | {precision} | {recall} | {f1}"


def render_markdown(report: EvaluationReport, *, verbose: bool = False) -> str:
    """Render the evaluation as Markdown, in Spanish like the rest of the documentation."""
    fields, verdicts, mails = report.fields, report.verdicts, report.mails
    extraction = total_score(fields.scores)
    lines = [
        "# Evaluación frente al gold standard",
        "",
        f"- Gold: versión {report.gold_version or '—'}, revisión: {report.gold_review or '—'}.",
        f"- {report.shipments} expedientes y {mails.primary.total} correos.",
        "- Entre corchetes, el intervalo de confianza de Wilson al 95 %.",
        "",
        "## Resumen",
        "",
        "| Métrica | Resultado |",
        "|---|---|",
        f"| Precisión de la asociación automática | {_proportion(mails.automatic_precision)} |",
        f"| Correos resueltos sin revisión | {_proportion(mails.automatic_coverage)} |",
        f"| Exactitud de la clase principal | {_proportion(mails.primary)} |",
        f"| Precisión de la extracción (micro) | {_pct(extraction.precision)} "
        f"{_interval(extraction.precision_interval)} |",
        f"| Recall de la extracción (micro) | {_pct(extraction.recall)} "
        f"{_interval(extraction.recall_interval)} |",
        f"| Veredicto exacto | {_proportion(verdicts.overall)} |",
        f"| Precisión al detectar lo que pide acción | {_pct(verdicts.actionable.precision)} "
        f"{_interval(verdicts.actionable.precision_interval)} |",
        f"| Recall al detectar lo que pide acción | {_pct(verdicts.actionable.recall)} "
        f"{_interval(verdicts.actionable.recall_interval)} |",
        "",
        "«Lo que pide acción» son los veredictos `ERP_ERROR`, `DISCREPANCY` y `ERP_MISSING`; "
        "un acierto exige el veredicto exacto.",
        "",
        "## Extracción por campo",
        "",
        "| Campo | Esperados | Dados | Aciertos | Precisión | Recall | F1 | Clasificador |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, score in fields.scores.items():
        classifier = _proportion(fields.classifier[name]) if name in fields.classifier else "—"
        lines.append(f"| {name} | {_score_cells(score)} | {classifier} |")
    lines += [
        "",
        "El clasificador (planificado, estimado o real) se puntúa sobre los valores acertados.",
        "",
        "## Veredicto por campo",
        "",
        "| Campo | Acierto |",
        "|---|---|",
        *(f"| {name} | {_proportion(p)} |" for name, p in verdicts.by_field.items()),
        "",
        "## Por veredicto",
        "",
        "| Veredicto | En el gold | Del sistema | Aciertos | Precisión | Recall | F1 |",
        "|---|---|---|---|---|---|---|",
        *(f"| `{code}` | {_score_cells(s)} |" for code, s in verdicts.by_verdict().items()),
        "",
        "## Clasificación por clase",
        "",
        "Cuenta cada clase de cada correo, principal o secundaria.",
        "",
        "| Clase | En el gold | Del sistema | Aciertos | Precisión | Recall | F1 |",
        "|---|---|---|---|---|---|---|",
        *(f"| {name} | {_score_cells(s)} |" for name, s in mails.by_class.items()),
        "",
        "## Asociación",
        "",
        "| Resultado | Correos |",
        "|---|---|",
        *(f"| {label} | {mails.association[key]} |" for key, label in _ASSOCIATION_LABELS.items()),
    ]
    if mails.unpaired:
        lines += ["", f"{mails.unpaired} correos del gold no se encontraron en la ejecución."]
    lines += _diagnosis(report)
    if verbose:
        lines += [
            "",
            "## Fallos (solo para uso local: nombran expedientes)",
            "",
            "| Unidad | Expediente | Campo | Esperado | Obtenido |",
            "|---|---|---|---|---|",
            *(
                f"| {m.unit} | {m.shipment_id} | {m.field} | {m.expected} | {m.got} |"
                for m in report.mismatches
            ),
        ]
    return "\n".join(lines) + "\n"


def _diagnosis(report: EvaluationReport) -> list[str]:
    """Where the values and verdicts are lost, and which tier resolves each value."""
    fields, verdicts, mails = report.fields, report.verdicts, report.mails
    lines = [
        "",
        "## Diagnóstico: dónde se pierde cada valor",
        "",
        "Cada valor que espera el gold, según la etapa que lo pierde. «Leído, no elegido»: "
        "alguna observación tenía el valor correcto, pero la proyección eligió otro o ninguno. "
        "«De más»: el sistema da un valor que el gold no espera.",
        "",
        "| Campo | " + " | ".join(_STAGES.values()) + " |",
        "|---|" + "---|" * len(_STAGES),
    ]
    totals: Counter[str] = Counter()
    for name, stages in fields.stages.items():
        totals.update(stages)
        lines.append(f"| {name} | " + " | ".join(str(stages[k]) for k in _STAGES) + " |")
    lines.append("| **Total** | " + " | ".join(f"**{totals[k]}**" for k in _STAGES) + " |")
    lines += [
        "",
        "## Diagnóstico: qué escalón resuelve cada valor",
        "",
        "| Escalón | Zona | Correctos | Erróneos |",
        "|---|---|---|---|",
    ]
    keys = sorted({(tier, zone) for tier, zone, _ in fields.resolution})
    for tier, zone in keys:
        right, wrong = fields.resolution[tier, zone, True], fields.resolution[tier, zone, False]
        zone_label = "—" if zone == UNRESOLVED else _ZONE_LABELS.get(zone, zone)
        lines.append(f"| {_TIER_LABELS.get(tier, tier)} | {zone_label} | {right} | {wrong} |")
    lines += [
        "",
        f"Precisión de lo aceptado sin revisión: {_proportion(fields.automatic_precision)}.",
        "",
        "## Diagnóstico: veredictos y clases",
        "",
        f"- Veredictos erróneos porque el valor ya lo era: {verdicts.causes['value']}.",
        f"- Veredictos erróneos con el valor correcto (reconciliación): "
        f"{verdicts.causes['reconciliation']}.",
    ]
    lines += [
        f"  - `{expected}` dado como `{got}`: {n}"
        for (expected, got), n in verdicts.reconciliation_errors.most_common()
    ]
    lines.append("- Clase principal confundida (gold → sistema):")
    lines += [
        f"  - {expected} → {got}: {n}"
        for (expected, got), n in mails.primary_confusion.most_common()
    ]
    return lines


def _score_json(s: Score) -> dict[str, Any]:
    return {
        "tp": s.tp,
        "fp": s.fp,
        "fn": s.fn,
        "precision": s.precision,
        "recall": s.recall,
        "f1": s.f1,
        "precision_interval": s.precision_interval,
        "recall_interval": s.recall_interval,
    }


def _proportion_json(p: Proportion) -> dict[str, Any]:
    return {"right": p.right, "total": p.total, "rate": p.rate, "interval": p.interval}


def _scores_json(scores: Mapping[str, Score]) -> dict[str, Any]:
    return {name: _score_json(s) for name, s in scores.items()}


def report_to_json(report: EvaluationReport, *, verbose: bool = False) -> dict[str, Any]:
    """Turn the evaluation into plain data."""
    fields, verdicts, mails = report.fields, report.verdicts, report.mails
    data: dict[str, Any] = {
        "gold": {"version": report.gold_version, "review": report.gold_review},
        "shipments": report.shipments,
        "fields": {
            "micro": _score_json(total_score(fields.scores)),
            "by_field": _scores_json(fields.scores),
            "classifier": {k: _proportion_json(p) for k, p in fields.classifier.items()},
            "stages": {k: dict(v) for k, v in fields.stages.items()},
            "resolution": [
                {"tier": tier, "zone": zone, "right": right, "count": n}
                for (tier, zone, right), n in sorted(fields.resolution.items())
            ],
            "automatic_precision": _proportion_json(fields.automatic_precision),
        },
        "verdicts": {
            "overall": _proportion_json(verdicts.overall),
            "by_field": {k: _proportion_json(p) for k, p in verdicts.by_field.items()},
            "by_verdict": _scores_json(verdicts.by_verdict()),
            "actionable": _score_json(verdicts.actionable),
            "confusion": [
                {"gold": gold, "system": got, "count": n}
                for (gold, got), n in sorted(verdicts.confusion.items())
            ],
            "causes": dict(verdicts.causes),
            "reconciliation_errors": [
                {"gold": gold, "system": got, "count": n}
                for (gold, got), n in sorted(verdicts.reconciliation_errors.items())
            ],
        },
        "mails": {
            "primary_class": _proportion_json(mails.primary),
            "primary_confusion": [
                {"gold": gold, "system": got, "count": n}
                for (gold, got), n in sorted(mails.primary_confusion.items())
            ],
            "by_class": _scores_json(mails.by_class),
            "association": dict(mails.association),
            "automatic_precision": _proportion_json(mails.automatic_precision),
            "automatic_coverage": _proportion_json(mails.automatic_coverage),
            "unpaired": mails.unpaired,
        },
    }
    if verbose:
        data["mismatches"] = [
            {
                "unit": m.unit,
                "shipment": m.shipment_id,
                "field": m.field,
                "expected": m.expected,
                "got": m.got,
            }
            for m in report.mismatches
        ]
    return data
