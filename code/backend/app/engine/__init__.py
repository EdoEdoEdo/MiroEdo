"""
Engine package: core simulation+report logic extracted from MiroFish,
made Flask-independent and Zep-optional, designed to be used as a library
by MiroEdo's FastAPI backend.

Layout:
  engine/
    config.py            # EngineConfig (replaces MiroFish Config class)
    utils/
      logger.py          # get_logger (no Flask)
      locale.py          # minimal i18n (IT/EN/ZH), no Flask
      llm_client.py      # OpenAI-compatible LLM wrapper
      zep_paging.py      # Zep node/edge paging helpers
    logging/
      action_logger.py   # per-platform JSONL action logger
    ipc/
      simulation_ipc.py  # file-based IPC for interview commands
    zep/                 # OPTIONAL — only loaded if Zep is configured
      entity_reader.py
      tools.py
    profile/
      generator.py       # OasisProfileGenerator (Brandwatch + Zep? → persona)
    simulation/
      config_generator.py
      runner.py          # SimulationRunner (orchestrates subprocess)
      worker.py          # standalone subprocess entrypoint (was run_parallel_simulation.py)
    report/
      agent.py           # ReportAgent (ReACT loop with tools)
"""
