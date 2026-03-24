

<p align="center">
  <img src="./img/banner.gif" alt="Atena: Decision Tree Agentic Framework">
</p>


> **⚠️ Atena is in beta!**
>
> If you encounter any issues, please [open an issue on GitHub](https://github.com/weaviate/elysia/issues).

[![PyPI Downloads](https://static.pepy.tech/badge/elysia-ai)](https://pepy.tech/projects/elysia-ai) [![Demo](https://img.shields.io/badge/Check%20out%20the%20demo!-yellow?&style=flat-square&logo=react&logoColor=white)](https://elysia.weaviate.io/)

Atena is an agentic platform designed to use tools in a decision tree, forked from [Elysia](https://github.com/weaviate/elysia). A decision agent decides which tools to use dynamically based on its environment and context. You can use custom tools or use the pre-built tools designed to retrieve your data in a Weaviate cluster.

[Read the docs!](https://weaviate.github.io/elysia/)

> 💡 Don't forget to check out [the Github Repository for the Frontend](https://github.com/weaviate/elysia-frontend)!

Installation is as simple as:
```bash
pip install elysia-ai
```

<p align="center">
  <img src="./img/elysia.gif" alt="Demo of Atena" width="85%">
</p>

### Watch the original Elysia video here:

<p align="center">
  <a href="https://youtu.be/PhCrlpUwEhU?si=rnJVBziKTEdPJiKz">
    <img src="./img/thumbnail.png" alt="https://youtu.be/PhCrlpUwEhU?si=rnJVBziKTEdPJiKz" width="70%">
  </a>
</p>

## Table of Contents

- [Get started (App)](#get-started-app)
- [Get Started (Python)](#get-started-python)
- [Installation](#installation-bash-linuxmacos)
  - [PyPi (Recommended)](#pypi-recommended)
  - [GitHub](#github)
  - [Configuring Settings](#configuring-settings)
- [Architecture](#architecture)
- [Open Source Spirit](#open-source-spirit-)
- [FAQ](#faq)


## Get started (App)

Run the app via

```bash
elysia start
```
Then head to `localhost:8090` in a browser, navigate to the settings page, add your required API keys, Weaviate cloud cluster details and specify your models. Optionally use `--port` to specify which port Atena will be run on.

The upstream project has a demo version (rate-limited, fixed datasets) at: https://elysia.weaviate.io/

## Get Started (Python)

To use Atena, you need to either set up your models and API keys in your `.env` file, or specify them in the config. [See the setup page to get started.](https://weaviate.github.io/elysia/setting_up/)

Atena can be used very simply:
```python
from elysia import tool, Tree

tree = Tree()

@tool(tree=tree)
async def add(x: int, y: int) -> int:
    return x + y

tree("What is the sum of 9009 and 6006?")
```

Atena is pre-configured to be capable of connecting to and interacting with your [Weaviate](https://weaviate.io/deployment/serverless) clusters!
```python
import elysia
tree = elysia.Tree()
response, objects = tree(
    "What are the 10 most expensive items in the Ecommerce collection?",
    collection_names = ["Ecommerce"]
)
```
This will use the built-in open source _query_ tool or _aggregate_ tool to interact with your Weaviate collections. To get started connecting to Weaviate, [see the setting up page in the docs](https://weaviate.github.io/elysia/setting_up/).

## Installation (bash) (Linux/MacOS)

### PyPi (Recommended)

Atena requires Python 3.12:
- [Installation via brew (macOS)](https://formulae.brew.sh/formula/python@3.12)
- [Installation via installer (Windows)](https://www.python.org/downloads/release/python-3120/)
- [Installation (Ubuntu)](https://ubuntuhandbook.org/index.php/2023/05/install-python-3-12-ubuntu/)

Optionally create a virtual environment via
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Then simply run 
```bash
pip install elysia-ai
```
to install straight away!

### GitHub

To get the latest development version, you can clone the github repo by running
```bash
git clone https://github.com/weaviate/elysia
```
move to the working directory via
```bash
cd elysia
```
Create a virtual environment with Python (version 3.10 - 3.12)
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```
and then install Atena via pip
```bash
pip install -e .
```
Done! You can now use the Atena python package

### Configuring Settings

<p align="center">
  <img src="./img/config.png" alt="Settings page"/>
</p>

To use Atena with Weaviate, i.e. for agentic searching and retrieval, you need to either have a *locally running* instance of Weaviate, or access to a *Weaviate cloud cluster* via an api key and URL. This can be specific in the app directly (see above image), or by creating a `.env` file with
```
WCD_URL=...
WCD_API_KEY=...
WEAVIATE_IS_LOCAL=... # True or False
```
Atena will automatically detect these when running locally, and this will be the default Weaviate cluster for all users logging into the Atena app. But these can be configured on a user-by-user basis through the config.

Whichever vectoriser you use for your Weaviate collection you will need to specify your corresponding API key, e.g.
```
OPENAI_API_KEY=...
```
These will automatically be added to the headers for the Weaviate client.

Same for whichever model you choose for the LLM in Atena, so if you are using GPT-4o, for example, specify an `OPENAI_API_KEY`.

Atena's recommended config is to use [OpenRouter](https://openrouter.ai/) to give easy access to a variety of models. So this requires
```
OPENROUTER_API_KEY=...
```

## Architecture

Atena is architectured as a modern web application with a full-featured frontend for a responsive, real-time interface and a FastAPI backend serving both the web interface and API. The core logic is written in pure Python – what we call "blood, sweat, and tears" custom logic – with DSPy handling LLM interactions. 

Unlike simple agentic platforms which have access to all possible tools at runtime, Atena has a pre-defined web of possible nodes, each with a corresponding action. Each node in the tree is orchestrated by a decision agent with global context awareness about its environment and its available options. The decision agent evaluates its environment, available actions, past actions and future actions to strategize the best tool to use.

Read more about how the original Elysia was built in [this blog](https://weaviate.io/blog/elysia-agentic-rag).

<p align="center">
  <img src="./img/architecture.png" alt="Architecture Diagram"/>
</p>


## Open Source Spirit ✨

**Weaviate** is proud to offer this open source project for the community. While we strive to address issues as fast as we can, please understand that it may not be maintained with the same rigor as production software. We welcome and encourage community contributions to help keep it running smoothly. Your support in fixing open issues quickly is greatly appreciated.


See the full [contributor guidelines](CONTRIBUTING.md) to see how you can get started contributing to Atena!

## FAQ

<details>
<summary><b>How do I use Atena with my own data?</b></summary>

You can connect to your own Weaviate cloud cluster, which will automatically identify any collections that exist in the cluster.

Collections require being _preprocessed_ for Atena. In the app, you just click the 'analyze' button in the Data tab. In Python you can do:

```python
from elysia.preprocessing.collection import preprocess

preprocess(collection_names=["YourCollectionName"])
```

</details>


<details>
<summary><b>Can I run Atena completely locally? (Locally running Weaviate, local models)</b></summary>

Yes!

You can connect to a locally running Weaviate instance in Docker, and connect to Ollama for locally running language models.
[See the setup page to get started.](https://weaviate.github.io/elysia/setting_up/)

</details>

<details>
<summary><b>Help! My local model isn't working with Atena. It's timing out or there are errors.</b></summary>

Atena works with quite long context, so some smaller models will struggle with this - it will either take a very long time to complete or the model will error to output the correct structured response.

For a complete guide and troubleshooting, [see this page of the documentation](https://weaviate.github.io/elysia/Advanced/local_models/).

</details>

<details>
<summary><b>How do I clear all my Atena data?</b></summary>

Everything Atena doesn't store locally will be a collection in your Weaviate cluster. You can delete any collections that start with `ELYSIA_` to reset all your Atena data.

For example, in Python:
```python
from elysia.util.client import ClientManager()
with ClientManager().connect_to_client() as client:
    for collection_name in client.collections.list_all():
        if collection_name.startswith("ELYSIA_"):
            client.collections.delete(collection_name)
```
</details>


<details>

<summary><b>Can I contribute to Atena?</b></summary>

Atena is **fully open source**, so yes of course you can! Clone and create a new branch of Atena via
```bash
git clone https://github.com/weaviate/elysia
git checkout -b <branch_name>
```
Make your changes, push them to your branch, go to GitHub and submit a pull request.

</details>


<details>
<summary><b>Where is the best place I can start contributing?</b></summary>

There are no 'huge' new features we are planning for Atena (for the moment). You could start with creating a new tool, or multiple new tools to create a custom workflow for something specific. Look for pain points you experience from your user journey and find what exactly is causing these. Then try to fix them or create an alternative way of doing things!

</details>
