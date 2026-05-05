# Example: Lexical Substitution Monitoring

This example is a topic seed for testing GapForge on language-monitoring and distribution-shift questions.

## Topic

```text
lexical substitution monitoring
```

## Suggested Run

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge run "lexical substitution monitoring" --max-papers 12
gapforge report
```

## Questions To Ask The Artifacts

- Do the clusters distinguish detection, benchmarks, evaluation metrics, and deployment assumptions?
- Do paper notes clearly mark abstract-only evidence?
- Does gap mining avoid claiming a monitoring gap without linked papers or an explicit indirect-evidence reason?
- Does the novelty gate leave uncertain ideas as `unknown` instead of overclaiming?

## Caution

The offline path is for reproducible smoke testing. Use live source searches and full-text reading before treating any generated gap as research-grade.
