# Random Concepts and Hands On

This repository is a multi-project learning workspace. It collects hands-on projects, course assignments, algorithm practice, machine learning experiments, computer vision exercises, and full-stack applications in one place.

Because the repo contains many independent projects, the best way to use it is to treat each top-level folder as its own project area. Most larger projects include their own README with deeper setup notes, architecture diagrams, commands, and tests.

## Repository Map

| Area | Path | What it contains |
| --- | --- | --- |
| Production-style backend and data systems | [`crdt-collab-editor`](crdt-collab-editor), [`distributed-rate-limiter`](distributed-rate-limiter), [`event-sourcing-cqrs`](event-sourcing-cqrs), [`streaming-anomaly-pipeline`](streaming-anomaly-pipeline) | Larger Python projects focused on distributed systems, APIs, real-time sync, event sourcing, rate limiting, streaming, Kafka, Redis, ClickHouse, and testing. |
| Full-stack dashboard | [`order-management-dashboard`](order-management-dashboard) | Next.js dashboard that connects to the event sourcing/CQRS backend and includes authentication, order views, charts, and demo data. |
| Medical and ML pipelines | [`medical-image-pipeline`](medical-image-pipeline), [`100DaysofCode/Machine Learning`](100DaysofCode/Machine%20Learning), [`GaussianNaiveBayes`](GaussianNaiveBayes), [`Keras-Basics-for-Image-Data-Augmentation`](Keras-Basics-for-Image-Data-Augmentation) | Machine learning, computer vision, classification, medical imaging, Keras, PyTorch, scikit-learn, and notebook/script experiments. |
| AI coursework | [`A.I`](A.I) | Assignments and examples covering Wumpus World, Max Connect 4, probability, Bayesian networks, and related AI concepts. |
| Computer vision basics | [`Computer Vision Basics`](Computer%20Vision%20Basics) | MATLAB exercises covering image formation, color spaces, image regions, gradients, blurring, and related vision fundamentals. |
| 100 Days of Code archive | [`100DaysofCode`](100DaysofCode) | A broad practice archive with coding problems, full-stack apps, React projects, ML scripts, C++ exercises, styling demos, and small experiments. |
| Small web app | [`Newsletter-Sngnup`](Newsletter-Sngnup) | Node/Express newsletter signup app with static HTML and CSS. |

## Quick Start

Clone the repository and move into the project you want to run:

```bash
git clone <repo-url>
cd Random-Concepts-and-Hands-On
```

Then open the target folder and follow that project's README when one exists:

```bash
cd distributed-rate-limiter
```

For Python projects, the usual pattern is:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
pytest tests/ -v
```

For Node or Next.js projects, the usual pattern is:

```bash
npm install
npm run dev
```

Some projects use Docker Compose:

```bash
docker-compose up
```

Check the individual README before running commands because each project has different services, ports, and dependencies.

## Featured Projects

### [`crdt-collab-editor`](crdt-collab-editor)

A real-time collaborative text editor built around the Logoot CRDT algorithm. It demonstrates conflict-free replicated data types, vector clocks, offline support, delta sync on reconnect, WebSocket-based collaboration, and convergence testing.

Useful entry points:

- [`crdt/logoot.py`](crdt-collab-editor/crdt/logoot.py): core CRDT implementation.
- [`crdt/vector_clock.py`](crdt-collab-editor/crdt/vector_clock.py): vector clock support.
- [`server/app.py`](crdt-collab-editor/server/app.py): FastAPI/WebSocket server.
- [`tests`](crdt-collab-editor/tests): convergence, commutativity, idempotency, and delete/insert tests.

Common commands:

```bash
cd crdt-collab-editor
pip install -r requirements.txt
uvicorn server.app:app --reload
pytest tests/ -v
```

### [`distributed-rate-limiter`](distributed-rate-limiter)

A distributed rate limiter with a gRPC API and Redis-backed algorithms. It includes token bucket, sliding window, and fixed window strategies, Prometheus metrics, client code, tests, and benchmark tooling.

Useful entry points:

- [`proto/ratelimiter.proto`](distributed-rate-limiter/proto/ratelimiter.proto): gRPC service contract.
- [`server/limiter.py`](distributed-rate-limiter/server/limiter.py): rate limiting algorithms.
- [`server/grpc_server.py`](distributed-rate-limiter/server/grpc_server.py): gRPC server.
- [`benchmarks`](distributed-rate-limiter/benchmarks): Locust benchmark setup.

Common commands:

```bash
cd distributed-rate-limiter
docker-compose up
pytest tests/ -v
```

### [`event-sourcing-cqrs`](event-sourcing-cqrs)

An order management backend built with event sourcing and CQRS. It stores immutable events, rebuilds projections, models an order aggregate, and includes saga-style workflow orchestration.

Useful entry points:

- [`domain/events.py`](event-sourcing-cqrs/domain/events.py): domain event definitions.
- [`domain/aggregates/order.py`](event-sourcing-cqrs/domain/aggregates/order.py): order aggregate.
- [`store/event_store.py`](event-sourcing-cqrs/store/event_store.py): append-only event store.
- [`projections/order_projection.py`](event-sourcing-cqrs/projections/order_projection.py): read model projection.
- [`sagas/order_saga.py`](event-sourcing-cqrs/sagas/order_saga.py): saga orchestration.

Common commands:

```bash
cd event-sourcing-cqrs
docker-compose up
pytest tests/ -v
```

### [`order-management-dashboard`](order-management-dashboard)

A Next.js 14 order management dashboard designed to work with the `event-sourcing-cqrs` backend. It includes JWT authentication, protected routes, dashboard analytics, orders, customers, status actions, and offline demo data.

Useful entry points:

- [`src/app`](order-management-dashboard/src/app): Next.js App Router pages and route handlers.
- [`src/components`](order-management-dashboard/src/components): UI and chart components.
- [`src/lib/auth.ts`](order-management-dashboard/src/lib/auth.ts): JWT/session helpers.
- [`src/lib/api.ts`](order-management-dashboard/src/lib/api.ts): typed API helpers.

Common commands:

```bash
cd order-management-dashboard
npm install
npm run dev
```

Demo credentials are documented in the project README.

### [`streaming-anomaly-pipeline`](streaming-anomaly-pipeline)

An end-to-end streaming anomaly detection pipeline. It uses Kafka for ingestion, an Isolation Forest detector for real-time anomaly scoring, ClickHouse for analytics storage, and FastAPI for dashboard/API endpoints.

Useful entry points:

- [`pipeline/producer.py`](streaming-anomaly-pipeline/pipeline/producer.py): synthetic metrics producer.
- [`pipeline/consumer.py`](streaming-anomaly-pipeline/pipeline/consumer.py): Kafka consumer pipeline.
- [`detector/isolation_forest.py`](streaming-anomaly-pipeline/detector/isolation_forest.py): anomaly detector.
- [`pipeline/clickhouse_writer.py`](streaming-anomaly-pipeline/pipeline/clickhouse_writer.py): ClickHouse persistence.
- [`api/server.py`](streaming-anomaly-pipeline/api/server.py): dashboard API.

Common commands:

```bash
cd streaming-anomaly-pipeline
docker-compose up
pytest tests/ -v
```

### [`medical-image-pipeline`](medical-image-pipeline)

A medical imaging pipeline for multi-label chest X-ray pathology classification. It includes preprocessing for DICOM/PNG/JPEG files, PyTorch model code, inference, GradCAM explainability, evaluation, API endpoints, Docker support, and tests.

Useful entry points:

- [`pipeline/preprocessing.py`](medical-image-pipeline/pipeline/preprocessing.py): image preprocessing.
- [`model/classifier.py`](medical-image-pipeline/model/classifier.py): model definition.
- [`pipeline/inference.py`](medical-image-pipeline/pipeline/inference.py): inference and GradCAM path.
- [`api/server.py`](medical-image-pipeline/api/server.py): prediction API.

Common commands:

```bash
cd medical-image-pipeline
docker-compose up
pytest tests/ -v
```

## Machine Learning and AI Projects

### [`GaussianNaiveBayes`](GaussianNaiveBayes)

Contains a Gaussian Naive Bayes implementation and example datasets such as breast cancer, car evaluation, and Hayes-Roth data. The folder includes both a Python script and a Jupyter notebook.

### [`Keras-Basics-for-Image-Data-Augmentation`](Keras-Basics-for-Image-Data-Augmentation)

Introductory Keras image augmentation practice. It includes a Python script, notebook, and sample cat image data for trying augmentation workflows.

### [`100DaysofCode/Machine Learning/skin_cancer`](100DaysofCode/Machine%20Learning/skin_cancer)

Dermatologist AI mini project based on skin lesion classification. The README explains the melanoma/nevi/seborrheic keratosis classification task, dataset layout, evaluation categories, and result submission format.

### [`A.I`](A.I)

AI assignment workspace with:

- Max Connect 4 game logic and search.
- Wumpus World logic/rules exercises.
- Probability and Bayesian network examples.

## Computer Vision Basics

[`Computer Vision Basics`](Computer%20Vision%20Basics) contains MATLAB exercises grouped by topic:

| Folder | Focus |
| --- | --- |
| [`Color, Light & Image Formation`](Computer%20Vision%20Basics/Color,%20Light%20&%20Image%20Formation) | Color spaces, HSV channels, and image formation basics. |
| [`Computer Vision Overview`](Computer%20Vision%20Basics/Computer%20Vision%20Overview) | Image access and sub-region examples. |
| [`Low, Mid & High Level Vision`](Computer%20Vision%20Basics/Low,%20Mid%20&%20High%20Level%20Vision) | Blurring, gradients, and image filtering examples. |
| [`Mathematics for Computer Vision`](Computer%20Vision%20Basics/Mathematics%20for%20Computer%20Vision) | RGB channel alignment and mathematical foundations. |

These are mostly script-based exercises. Open the `.m` files in MATLAB or Octave-compatible tooling where possible.

## 100 Days of Code Archive

[`100DaysofCode`](100DaysofCode) is a large collection of practice work. It is best read as a learning archive rather than one single application.

### [`100DaysofCode/Problems`](100DaysofCode/Problems)

Python solutions for coding interview and algorithm problems, including array manipulation, strings, itinerary reconstruction, stock profit, duplicate removal, and other LeetCode-style exercises.

### [`100DaysofCode/Full Stack`](100DaysofCode/Full%20Stack)

Contains many small-to-medium web projects:

| Project | Description |
| --- | --- |
| `api-githubjobs-app` | Job search style app using API data. |
| `contact-us-form` | React/contact form project with a small server folder. |
| `D3 with React` | D3 chart examples in React, including bar and radial charts. |
| `docker-kubernetes` | Basic Node/Docker/Kubernetes practice. |
| `E-commerce` | Express/Mongo-style e-commerce backend and client folder. |
| `file-uploader` | File upload/gallery app with client and server. |
| `keeper-*` folders | React Keeper app practice projects in multiple stages. |
| `mern-exercise-tracker` | MERN exercise tracker with backend models and routes. |
| `pokedex` | TypeScript/browser Pokedex project. |
| `randomuser` | Random user data app. |
| `react-basics-brushup` | React fundamentals practice. |
| `reactportfolio` | Portfolio project with React and static assets. |
| `REST-api` | REST API practice. |
| `storybook_foundations` | Storybook practice project. |
| `todo-client` | TypeScript React todo client. |
| `todo_typescript-api` | TypeScript API for todos. |
| `user-search` | React/Redux user search app. |

Many of these projects have their own `package.json`. To run one, enter that project folder first and then use the scripts defined there.

### [`100DaysofCode/Machine Learning`](100DaysofCode/Machine%20Learning)

Contains regression/classification practice, preprocessing scripts, and the skin cancer image classification project.

### [`100DaysofCode/Other`](100DaysofCode/Other)

Contains smaller practice areas:

- `2D Histogram Filter`: C++ localization/histogram filter exercises.
- `CSS-Grid`: CSS Grid layout tasks.
- `Python Clean Code Practice`: Python cleanup and scraping practice.
- `Styling`: CSS/3D styling experiments.
- `webpack-babel-basics`: JavaScript build tooling practice.

## Small Web App

### [`Newsletter-Sngnup`](Newsletter-Sngnup)

A small Node/Express newsletter signup project with:

- [`app.js`](Newsletter-Sngnup/app.js): Express app entry point.
- [`signup.html`](Newsletter-Sngnup/signup.html): signup page.
- [`public/styles.css`](Newsletter-Sngnup/public/styles.css): styling.
- [`package.json`](Newsletter-Sngnup/package.json): Node dependencies/scripts.

Typical setup:

```bash
cd Newsletter-Sngnup
npm install
node app.js
```

## How to Navigate This Repo

Use this order if you are new to the repository:

1. Start with the table in [Repository Map](#repository-map).
2. Pick the topic you care about: distributed systems, AI/ML, computer vision, full-stack, or algorithms.
3. Open that folder's README if available.
4. Check for `requirements.txt`, `package.json`, `Dockerfile`, or `docker-compose.yml`.
5. Run the smallest local command first, usually tests or a development server.

Useful search commands:

```bash
# List all README files
find . -iname "readme*"

# List Python dependency files
find . -name "requirements.txt"

# List Node projects
find . -name "package.json" -not -path "*/node_modules/*"

# Search for a keyword
rg "event sourcing"
```

On Windows PowerShell, equivalent commands include:

```powershell
Get-ChildItem -Recurse -Filter README*
Get-ChildItem -Recurse -Filter requirements.txt
Get-ChildItem -Recurse -Filter package.json | Where-Object { $_.FullName -notlike "*node_modules*" }
rg "event sourcing"
```

## Common Technologies

This repo includes examples using:

- Python, FastAPI, PyTest, scikit-learn, PyTorch, Keras/TensorFlow.
- JavaScript, TypeScript, React, Next.js, Redux, Express.
- Docker, Docker Compose, Redis, PostgreSQL, Kafka, ClickHouse, Prometheus.
- gRPC, WebSockets, REST APIs.
- MATLAB/Octave-style computer vision scripts.
- C++ practice exercises.

## Notes for Contributors and Future Readers

- This is a collection of independent projects, so dependencies are not installed from the repo root.
- Some older learning projects may use older package versions or course starter code.
- Some folders contain generated artifacts, caches, datasets, or built files.
- Prefer adding a README inside each project folder when creating new work.
- For larger projects, include setup commands, ports, environment variables, test commands, and a short architecture explanation.

## Suggested README Template for New Folders

When adding a new project, use this small checklist:

````markdown
# Project Name

Short description of what the project does.

## Tech Stack

- Language/framework
- Database/services
- Testing tools

## How to Run

```bash
# commands here
```

## How to Test

```bash
# commands here
```

## Project Structure

- `src/`: main code
- `tests/`: tests
- `README.md`: project documentation
````

Keeping each project documented makes this single-repo setup much easier for other people to explore.
