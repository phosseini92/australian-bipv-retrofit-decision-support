# CC-002 — Break-even locked-source clarification

Status: **APPROVED FOR IMPLEMENTATION**  
Approval date: 2026-10-07  
Classification: research-method clarification  
Approved package: **D1-B + D2-A + D3-A**

## Trigger

The controlled Break-even implementation exposed three conflicts that could not
be resolved silently in code:

1. Analysis Specification Section 11.2 produced an initial-premium-only access
   threshold of A$14,017.27/event, while full discounted WLC equality—including
   premium-driven O&M—required A$14,886.98/event.
2. Section 11.5 required a “selected pairwise comparison” for `BE_r` without
   identifying variants A and B.
3. Research Design v2.0 named an intervention-frequency threshold, while the
   Analysis Specification and Input Table provided no corresponding output
   equation or monetary scenario.

These were recorded before implementation as BE-M01, BE-M02, and BE-M03. No
research choice was made in code while approval was pending.

## Approved D1-B — Full-WLC access threshold

The article-primary `BE_access` result is solved from full discounted WLC
equality:

`S_access,WLC* = [WLC_reversible − WLC_low − PV(EoL differential)] / Σ[f_fail/(1+r)^y]`

Under the central zero-EoL-differential scenario this equals
**A$14,886.98/event** for each matched reversible/low pair.

The literal Section 11.2 expression remains a clearly labelled
initial-premium-only diagnostic at **A$14,017.27/event**. It is not presented as
complete WLC break-even because it leaves A$1,708.90 of discounted WLC
unrecovered.

This clarification changes no central WLC input or cost schedule.

## Approved D2-A — Symmetric discount-rate comparison set

Primary `BE_r` analysis covers all four matched reversible/low pairs:

- V03 versus V01;
- V04 versus V02;
- V07 versus V05; and
- V08 versus V06.

Each pair solves `WLC_reversible(r) − WLC_low(r) = 0` over 0–15% real. A
non-existent root is reported explicitly for every pair. No representative pair
is privileged.

The full 12-pair one-factor matrix remains diagnostic. Mounting contrasts and
replacement-scope ties are not promoted to primary `BE_r` outputs.

## Approved D3-A — No independent intervention-frequency threshold

The Proceedings Break-even output is the required access/intervention saving
per event. Intervention frequency remains a bounded numerical OFAT reliability
input through `λ_mod`/`f_fail`; it is not a separate scalar threshold.

No empirical access-cost assumption, contractor tariff, or new frequency
equation is introduced.

## Impact assessment

- Variant definitions: no impact.
- Central energy/lifecycle/evidence/Pareto results: no impact.
- Central WLC: no impact.
- Numerical OFAT inputs and results: no impact.
- Break-even primary access label/value: updated under D1-B.
- Break-even discount-rate comparison set: completed under D2-A.
- Intervention-frequency output requirement: reconciled under D3-A.
- Baseline readiness: Break-even blocker may close only after all QA assertions
  pass on re-execution.

## Approval record

The user explicitly approved:

> D1-B + D2-A + D3-A را تأیید می‌کنم.

This approval authorises implementation of only the three decisions above. It
does not authorise unrelated research-model changes.
