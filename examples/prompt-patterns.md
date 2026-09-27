# Fresh Worker prompt patterns

Fresh Worker performs best when the delegated job is narrow, self-contained, and has an explicit output contract.

## Independent code review

```text
Independently review the code below.

Check only:
1. correctness;
2. race conditions;
3. resource cleanup;
4. cancellation behaviour.

Return:
- findings ordered by severity;
- file/line references where possible;
- "No material issue found" if none are found.

Do not redesign unrelated parts.

<code>
...
</code>
```

## Acceptance-criteria verifier

```text
Act as an independent verifier.

Artifact:
...

Acceptance criteria:
1. ...
2. ...
3. ...

For each criterion return PASS, FAIL, or NOT PROVEN and one short reason.
Do not infer evidence that is not present.
```

## Architecture second opinion

```text
Evaluate this architecture without assuming the author's conclusion is correct.

Goal:
...

Constraints:
...

Proposed design:
...

Identify:
- hidden assumptions;
- failure modes;
- simpler alternatives;
- the strongest argument in favour of the design;
- the strongest argument against it.

Finish with the unresolved questions, not a generic summary.
```

## Debugging hypothesis check

```text
We observe:
...

Current hypothesis:
...

Evidence:
...

Independently assess whether the evidence actually supports the hypothesis.
List competing explanations that fit the same evidence.
State what single next test would most distinguish them.
```

## Small-model delegation

For smaller local models, reduce scope even further:

```text
Check only whether this function can return a negative value.

Inputs are integers in [0, 1000].

Return exactly:
ANSWER: YES or NO
REASON: one paragraph

Function:
...
```

## Anti-patterns

Avoid references to unavailable parent context:

```text
Check what we discussed.
```

Avoid multiple unrelated jobs in one worker:

```text
Review the code, research competitors, rewrite the README, and design a logo.
```

Avoid asking for independent verification while feeding the worker only the parent's conclusion. Include the underlying evidence whenever practical.
