#import "@preview/polylux:0.4.0": *
#import "@preview/metropolis-polylux:0.1.0" as metropolis
#import metropolis: new-section, focus
#import "@preview/cades:0.3.0": qr-code

#show: metropolis.setup.with(
  text-font: "SF Pro Display",
  math-font: "InaiMathi",
  code-font: "JetBrains Mono",
  text-size: 21pt,
)

#slide[
  #set page(header: none, footer: none, margin: 3em)

  #text(size: 1.3em)[
    *Tamarin Python Wrapper*
  ]

  #metropolis.divider

  #set text(size: .8em, weight: "light")
  Luca Mandrelli

  June 26, 2025
]

#slide[
  = What will we talk about ?

  #metropolis.outline
]

#new-section[Why?]

#slide[
  = The problem

  - A lot of different use cases
  - A lot of different but specific solution (ut-tamarin, ANSSI wrapper...)
  - Specific solutions needed a development environment
]

#slide[
  #show: focus
  *Solution: Tamarin Wrapper*

  - Easy to install (currently via pip, future : Docker container)
  - Polyvalent : you describe a complete input, you can customize it widely
  - Complete error handling
]

#slide[
  = What Tamarin Wrapper Provides

  *Key Features:*

  - **Batch Execution**: Multiple models across different Tamarin versions
  - **JSON Configuration**: Simple, declarative execution recipes
  - **Progress Tracking**: Real-time updates, error handling
  - **Output Processing**: Structured JSON results with detailed summaries
]

#new-section[How does the config works ?]

#slide[
  = Configuration Structure

  *Three main sections:*

  ```json
  {
    "config": { /* Global system settings */ },
    "tamarin_versions": { /* Tamarin executables linked to an alias */ },
    "tasks": { /* Description of the wrapper work */ }
  }
  ```

  - **Declarative**: Describe what you want, not how
  - **Hierarchical**: Global → Task → Lemma settings
  - **Flexible**: Override settings at any level
]

#slide[
  = Global Configuration

  ```json
  {
    "config": {
      "global_max_cores": 8,
      "global_max_memory": 16,
      "default_timeout": 7200,
      "output_directory": "./results"
    }
  }
  ```

  *System-wide resource limits* : the wrapper will also warn the user in case of misconfiguration (ex 32GB set while system has 16GB)
]

#slide[
  = Tamarin Versions

  ```json
  {
    "tamarin_versions": {
      "stable": {
        "path": "tamarin-binaries/1.10.0/bin/tamarin-prover"
      },
      "dev": {
        "path": "tamarin-binaries/1.11.0/bin/tamarin-prover",
      }
    }
  }
  ```

  *Named aliases for different Tamarin executables*, the path can also be a symbolic link
]

#slide[
  = Task Configuration

  #text(size: 0.8em)[
  ```json
  {
    "tasks": {
      "wpa2_analysis": {
        "theory_file": "protocols/wpa2.spthy",
        "tamarin_versions": ["stable", "dev"],
        "output_file_prefix": "wpa2_results",
        "tamarin_options": ["-v"],
        "preprocess_flag": ["badKey"],
        "ressources": {
          "max_cores": 4,
          "max_memory": 8,
          "timeout": 3600
        }
      }
    }
  }
  ```
  This task will prove all the lemmas on the "stable" and "dev" versions of the tamarin-prover :
  ```sh
  tamarin-binaries/tamarin-prover-1.10/1.10.0/bin/tamarin-prover +RTS -N4 -RTS protocols/wpa2.spthy --prove -v -D="badKey"
  --output=results_26-06-25_11-38-24/models/wpa2_analysis_stable.spthy
  ```]
]

#slide[
  = Lemma-Level Configuration

  #grid(
    columns: (2fr, 1fr),
    column-gutter: 1em,
    align: (left, center),
    [
      #text(size:0.55em)[```json
      "tasks": {
    		"wpa2": {
    			"theory_file": "protocols/wpa2_four_way_handshake_unpatched.spthy",
    			"tamarin_versions": ["stable", "dev"],
    			"output_file_prefix": "WPA2_Example",
          "preprocess_flags": ["goodKey"],
          "tamarin_options" : ["-v"],
    			"ressources": {
    				"max_cores": 2,
    				"max_memory": 8,
            "timeout": 3600
    			},
          "lemmas" : [
    				{
    					"name": "nonce_reuse_key_type",
    					"tamarin_options":["--heuristic=S"],
    					"ressources": {
    						"max_cores": 1
    					}
    				},
    				{
    					"name": "authenticator_rcv_m2_must_be_preceded_by_snd_m1",
    					"tamarin_versions": ["stable"],
    					"preprocess_flags": ["badKey"],
    					"ressources": {
    						"max_memory": 16,
    						"timeout": 30
    					}
    				}
    		}
      ```]
    ],
    [
      #align(horizon)[
        *Per-lemma overrides with configuration inheritence*
        ```
        Global Config
            ↓
        Task Config (inherits & overrides)
            ↓
        Lemma Config (inherits & overrides)
        ```
      ]
    ]
  )
]

#new-section[High-Level Architecture]

#slide[
  = System Architecture Overview
  #grid(
    columns: (1.2fr, 1fr),
    column-gutter: 1.5em,
    align: (center, top),
    [
      #align(center)[
        #image("arch.png", height: 100%)
      ]
    ],
    [
      #text(size: 0.75em)[
        *Key modules and their roles:*

        - **`main.py`**: CLI entry point
        - **`runner.py`**: Coordination of the wrapper
        - **`config_manager.py`**: JSON loading and validation
        - **`task_manager.py`**: Individual task execution
        - **`process_manager.py`**: Low-level process control
        - **`resource_manager.py`**: Global resource tracking
        - **`output_manager.py`**: Result parsing and formatting
      ]
    ]
  )
]

#slide[
  = Core Components


]

#slide[
  = Output Structure

  ```
  output_directory/
  ├── success/
  │   ├── task_lemma_version.json
  │   └── ...
  ├── failed/
  │   ├── task_lemma_version.json
  │   └── ...
  └── models/
      ├── task_lemma_version.spthy
      └── ...
  ```

  *Organized results with clear success/failure separation*
]

#slide[
  = How to find the project

  #grid(
    columns: (2fr, 1fr),
    column-gutter: 2em,
    align: (left, center),
    [
      - On the team gitlab : #link("https://projects.cispa.saarland/cc/tamarin-wrapper")[https://projects.cispa.saarland/cc/tamarin-wrapper]
      - On PyPI, with the last stable version you can test

      You can give your ideas to add features to the wrapper with the gitlab issues:
      #link("https://projects.cispa.saarland/cc/tamarin-wrapper/-/issues")[https://projects.cispa.saarland/cc/tamarin-wrapper/-/issues]
    ],
    [
      #align(horizon)[
        #qr-code("https://projects.cispa.saarland/cc/tamarin-wrapper", width: 3cm)

        *GitLab Project*

        #v(1em)

        #qr-code("https://projects.cispa.saarland/cc/tamarin-wrapper/-/issues", width: 3cm)

        *GitLab Issues*
      ]
    ]
  )
]

#slide[
  #show: focus
  *Questions?*

  #grid(
    columns: (1fr),
    column-gutter: 2em,
    align: center,
    [
      #qr-code("https://pypi.org/project/tamarin-wrapper/", width: 4cm)

      *PyPI Package*
    ]
  )
]
