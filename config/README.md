# Locked configuration

Files use JSON syntax that is valid YAML 1.2. This keeps them human-readable and
lets the milestone 0.1 validation suite load them with the Python standard
library, without implicit YAML type coercion.

- `variants.yaml`: exact V01–V08 mapping.
- `input_schema.yaml`: machine-readable input-row contract.
- `model.yaml`: invariants, source bindings, mandatory execution order, Pareto
  criteria, and locked output filenames.
- `sensitivity.yaml`: OFAT inputs, structural runs, and out-of-scope runs.
- `qa_assertions.yaml`: exact Q01–Q14 registry with hard-fail policy.
