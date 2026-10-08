# Data and implementation scope

## Data availability

| Material | Package status |
|---|---|
| Manuscript aggregate results | Transcribed with table/page provenance |
| Six controlled fixtures | Source and local execution records included |
| Discovery task IDs and 1,200 source trajectories | Not included |
| Original 240 MAIN failure sites and snapshots | Not included |
| Original subset memberships and 120 REPLICATION sites | Not included |
| Original 63,408 linked records and retry ledger | Not included |
| Model outputs, prompts, seeds and native checkpoints | Not included |
| Exact framework commits, model/tokenizer revisions and selection tie order | Unavailable fields recorded as `null` |
| Native integrations for the four public frameworks | Not included |
| Supplementary material | Not provided |

## State backend

The backend captures a declared directory. It stores file contents, names, modes, modification times and symlink target text. It rejects hard links and special files. Semantic equality excludes timestamps. Symlink mtime and root-directory metadata are not captured.

Ownership, ACLs, extended attributes, process memory, open descriptors, shell state, background writers and external services are outside the capture boundary. Targets of links outside the directory are not copied. Fixture subprocesses terminate before snapshots; SQLite connections are closed. There is no generic live-database backup or writer-quiescence mechanism.

Branches reuse the same physical task path sequentially. Oracle evaluation uses a separate directory clone, which has a different absolute path. The local backend runs with host access rights and does not impose CPU, memory, disk, network or whole-filesystem isolation.

## Fixture operations

The package fixture runs a two-stage local wheel installation driver. The virtual-environment fixture interrupts after interpreter creation and before readiness configuration. The build fixture retains Python bytecode intermediates. Patch, database and generation fixtures execute their corresponding local operations. These are six controlled examples.

## Controllers

The structured tool interface counts each deliberation, tool action, rejection and completion response as an action. Token accounting uses adapter-reported generated counts. Tool output is capped at 8 KiB and inspection output at 2 KiB. Public frameworks' native action accounting and tokenizer-specific output limits are not implemented.

External adapters run as local processes. In-process adapters are callbacks; the engine does not forcibly preempt arbitrary callback execution. Reference repairs and scripted examples do not invoke a language model.

## Analysis and figures

The aggregate audit checks arithmetic over manuscript values. Repository-cluster intervals require linked run records. The implemented p-value method is a two-sided centered-bootstrap approximation with Holm adjustment; the manuscript does not specify its original p-value algorithm.

The numeric source omits Figure 7(b) stratum values, some Figure 9(b) controller/budget rates and the PRE value for one inspection condition. Generated figures use available values, with captions identifying the plotted quantities.

## Execution coverage

Local verification used Windows and Python 3.11. Original-scale model inference, Linux CI and the Docker image were not executed locally.
