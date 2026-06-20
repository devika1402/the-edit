# Troubleshooting

The problems that took time to work out, with how each one was found and fixed. These are the parts a reviewer tends to ask about, so they are written up rather than buried.

## The staging table that built empty

The transactions loaded fine, 31,788,324 rows in `raw_transactions`, but `stg_transactions` came back empty even though the query had scanned 3.24 GB. An empty table from a query that clearly read the data is a strange place to land.

The cause was the dataset's history. It had spent a short time as a BigQuery sandbox, and the sandbox sets a 60-day default expiration on every table partition. The transactions span 2018 to 2020, so when staging wrote partitions dated two years in the past, every one of them was already past its expiry and was dropped on write. The query worked, the data went in, and the partitions vanished immediately.

The fix was to clear the dataset's default expirations in `ensure_dataset`, which is idempotent and runs on every load, and to set the partition expiration to none in the staging SQL itself. Staging rebuilt green after that, and the row count matched the source.

## The ranker that scored worse than popularity

The first comparison was alarming. The learned ranker came in at a hit-rate of 0.34 against popularity at 0.57. A trained model losing to sorting by popularity usually means something is wired wrong, not that the model is bad.

It was wired wrong. CatBoost needs each customer's rows grouped together, so the candidate matrix is sorted by customer before scoring. The bug was that the predicted scores were being written back onto the unsorted matrix while the model had scored the sorted one, so every customer's scores landed on the wrong rows. The rankings were scrambled.

The fix was to predict and assign on the same sorted frame, so the scores align with the rows they belong to. A regression test (`tests/test_ranker_predict.py`) trains a tiny model and asserts the alignment, so this cannot come back unnoticed. After the fix the ranker beat both baselines by a wide margin.

## The age band that scored near zero

The per-segment report showed an "unknown" age band at MAP@12 of about 0.0006 across every model, far below every answerable band. A group that bad looks like a fairness problem with customers who have no age recorded.

It was not about age. Two things were tangled. The "unknown" bucket held about 1,150 customers, but only 65 were actually missing an age. The other roughly 1,100 were cold customers with no purchase history, who were being dropped by the training matrix's inner join and then mislabelled as age-unknown by the metric. Worse, those cold customers were getting no recommendation at all, so their average precision was zero for every model.

The fix had two parts. Cold customers now get a popularity fallback rather than an empty list, defined once and shared by evaluation, guardrails, and serving. The parity report now segments on the true age band from the customer table, which covers cold customers too. With both in place the "unknown" band is 65 customers at a normal score, and the underlying story, that cold customers are served by popularity, shows up as its own warm-versus-cold cohort.

## The numbers that move between runs

Running the whole pipeline twice gives slightly different headline numbers, a ranker MAP@12 of 0.0305 on one run and 0.0292 on another, with the warm and cold customer counts shifting too.

The cause is tie-breaking. Retrieval takes the top N items by a count, and when several items tie on that count, BigQuery is free to break the tie either way. Different ties picked means a slightly different candidate set, which shifts which customers are testable and the final score. The conclusion is steady, the ranker wins decisively each time, but the exact number is not reproducible to the last digit. The fix, not yet applied, is to add an explicit secondary sort key to the retrieval selections so ties always break the same way.

## Setup snags worth knowing

Two install problems cost time before any code ran.

The Homebrew install of the Google Cloud SDK failed because the default Python on the machine was 3.14, which has a binary mismatch with the system XML library, so the SDK's virtualenv step crashed. The fix was the standalone SDK installer, which bundles its own Python and sidesteps the issue.

The Kaggle download failed twice. First with a 403, because the competition rules have to be accepted in the browser before the API will serve the files. Then because the `--unzip` flag was removed from the current Kaggle CLI, so the files download as a zip and have to be unzipped as a separate step. The full setup path is written up in [SETUP.md](SETUP.md).

## Memory, avoided rather than fixed

The training plan first pulled the whole candidate-feature matrix, about 40 million rows, into pandas and then sampled it. That would run a laptop out of memory. The sampling and the negative-capping were pushed into the SQL instead, so only about 1.4 million training rows and 3.1 million validation rows ever come back to Python. The lesson stuck: sample in the warehouse, not in pandas.
