PS &lt;project-dir&gt;> python -m pytest tests/ -v
================================================= test session starts =================================================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0 -- &lt;python-path&gt;
cachedir: .pytest_cache
rootdir: &lt;project-dir&gt;
configfile: pyproject.toml
plugins: anyio-4.12.1, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 508 items

tests/test_api_server.py::test_health_check PASSED                                                               [  0%]
tests/test_api_server.py::test_list_providers PASSED                                                             [  0%]
tests/test_api_server.py::test_get_sessions PASSED                                                               [  0%]
tests/test_api_server.py::test_clear_sessions PASSED                                                             [  0%]
tests/test_api_server.py::test_list_memory PASSED                                                                [  0%]
tests/test_api_server.py::test_save_and_delete_memory PASSED                                                     [  1%]
tests/test_api_server.py::test_list_tools PASSED                                                                 [  1%]
tests/test_api_server.py::test_get_project_docs PASSED                                                           [  1%]
tests/test_api_server.py::test_project_status PASSED                                                             [  1%]
tests/test_api_server.py::test_chat_requires_message PASSED                                                      [  1%]
tests/test_api_server.py::test_provider_switch_invalid PASSED                                                    [  2%]
tests/test_api_server.py::test_invalid_doc_update PASSED                                                         [  2%]
tests/test_api_server.py::test_cors_headers PASSED                                                               [  2%]
tests/test_auto_commit.py::test_manager_creates PASSED                                                           [  2%]
tests/test_auto_commit.py::test_singleton_exists PASSED                                                          [  2%]
tests/test_auto_commit.py::test_watch_snapshots PASSED                                                           [  3%]
tests/test_auto_commit.py::test_commit_if_success_no_changes PASSED                                              [  3%]
tests/test_auto_commit.py::test_staged_diff PASSED                                                               [  3%]
tests/test_background.py::test_background_run_and_status FAILED                                                  [  3%]
tests/test_background.py::test_background_list_tasks PASSED                                                      [  3%]
tests/test_background.py::test_background_cancel PASSED                                                          [  4%]
tests/test_background.py::test_background_status_not_found PASSED                                                [  4%]
tests/test_background.py::test_background_callback PASSED                                                        [  4%]
tests/test_background.py::test_background_failed_command PASSED                                                  [  4%]
tests/test_background.py::test_background_active_count PASSED                                                    [  4%]
tests/test_background.py::test_background_clean_old PASSED                                                       [  5%]
tests/test_benchmark.py::test_benchmark_minimum_accuracy PASSED                                                  [  5%]
tests/test_benchmark.py::test_benchmark_confidence_above_zero PASSED                                             [  5%]
tests/test_benchmark.py::test_benchmark_no_crashes PASSED                                                        [  5%]
tests/test_cache.py::test_stable_hash_deterministic PASSED                                                       [  5%]
tests/test_cache.py::test_stable_hash_order_independent PASSED                                                   [  6%]
tests/test_cache.py::test_cache_store_set_get PASSED                                                             [  6%]
tests/test_cache.py::test_cache_store_miss PASSED                                                                [  6%]
tests/test_cache.py::test_cache_store_expiry PASSED                                                              [  6%]
tests/test_cache.py::test_cache_store_lru_eviction PASSED                                                        [  6%]
tests/test_cache.py::test_cache_store_invalidate PASSED                                                          [  7%]
tests/test_cache.py::test_cache_store_invalidate_pattern PASSED                                                  [  7%]
tests/test_cache.py::test_cache_store_stats PASSED                                                               [  7%]
tests/test_cache.py::test_response_cache_key_consistent PASSED                                                   [  7%]
tests/test_cache.py::test_response_cache_key_different PASSED                                                    [  7%]
tests/test_cache.py::test_response_cache_set_get PASSED                                                          [  8%]
tests/test_cache.py::test_response_cache_temperature_skip PASSED                                                 [  8%]
tests/test_cache.py::test_tool_cache_key_consistent PASSED                                                       [  8%]
tests/test_cache.py::test_tool_cache_key_different PASSED                                                        [  8%]
tests/test_cache.py::test_tool_cache_set_get PASSED                                                              [  8%]
tests/test_cache.py::test_tool_cache_short_ttl_bash PASSED                                                       [  9%]
tests/test_cache.py::test_tool_cache_invalidate_on_write PASSED                                                  [  9%]
tests/test_check_cli.py::test_doctor_runs_without_error PASSED                                                   [  9%]
tests/test_check_cli.py::test_cli_app_has_provider PASSED                                                        [  9%]
tests/test_check_cli.py::test_cli_app_has_state PASSED                                                           [  9%]
tests/test_check_cli.py::test_cli_app_cmds_registered PASSED                                                     [ 10%]
tests/test_checkpoint.py::test_checkpoint_manager_creates PASSED                                                 [ 10%]
tests/test_checkpoint.py::test_checkpoint_manager_no_crash_without_git PASSED                                    [ 10%]
tests/test_checkpoint.py::test_checkpoint_list_no_crash PASSED                                                   [ 10%]
tests/test_checkpoint.py::test_checkpoint_count PASSED                                                           [ 10%]
tests/test_checkpoint.py::test_singleton_exists PASSED                                                           [ 11%]
tests/test_cli_all.py::test_cli_command[/help-False] PASSED                                                      [ 11%]
tests/test_cli_all.py::test_cli_command[/clear-False] PASSED                                                     [ 11%]
tests/test_cli_all.py::test_cli_command[/model-False] PASSED                                                     [ 11%]
tests/test_cli_all.py::test_cli_command[/provider opencode-zen-False] PASSED                                     [ 11%]
tests/test_cli_all.py::test_cli_command[/tools-False] PASSED                                                     [ 12%]
tests/test_cli_all.py::test_cli_command[/skills-False] PASSED                                                    [ 12%]
tests/test_cli_all.py::test_cli_command[/history-False] PASSED                                                   [ 12%]
tests/test_cli_all.py::test_cli_command[/save-False] PASSED                                                      [ 12%]
tests/test_cli_all.py::test_cli_command[/load .-False] PASSED                                                    [ 12%]
tests/test_cli_all.py::test_cli_command[/export-False] PASSED                                                    [ 12%]
tests/test_cli_all.py::test_cli_command[/remember test-fact-from-cli-test-False] PASSED                          [ 13%]
tests/test_cli_all.py::test_cli_command[/memories-False] PASSED                                                  [ 13%]
tests/test_cli_all.py::test_cli_command[/manifest-False] PASSED                                                  [ 13%]
tests/test_cli_all.py::test_cli_command[/reasoning-False] PASSED                                                 [ 13%]
tests/test_cli_all.py::test_cli_command[/debug-False] PASSED                                                     [ 13%]
tests/test_cli_all.py::test_cli_command[/doctor-False] PASSED                                                    [ 14%]
tests/test_cli_all.py::test_cli_command[/undo-False] PASSED                                                      [ 14%]
tests/test_cli_all.py::test_cli_command[/proxy-False] PASSED                                                     [ 14%]
tests/test_cli_all.py::test_cli_command[/sandbox .-False] PASSED                                                 [ 14%]
tests/test_cli_all.py::test_cli_command[/mcp-False] PASSED                                                       [ 14%]
tests/test_cli_all.py::test_cli_command[/gguf-False] PASSED                                                      [ 15%]
tests/test_cli_all.py::test_cli_command[/branch list-False] PASSED                                               [ 15%]
tests/test_cli_all.py::test_cli_command[/version-False] PASSED                                                   [ 15%]
tests/test_cli_all.py::test_cli_command[/permissions-False] PASSED                                               [ 15%]
tests/test_cli_all.py::test_cli_command[/apikey show-False] PASSED                                               [ 15%]
tests/test_cli_all.py::test_exit_command PASSED                                                                  [ 16%]
tests/test_cron_job.py::test_cron_job_defaults PASSED                                                            [ 16%]
tests/test_cron_job.py::test_cron_job_to_from_dict PASSED                                                        [ 16%]
tests/test_cron_job.py::test_cron_job_status_enum PASSED                                                         [ 16%]
tests/test_cron_job.py::test_cron_job_to_from_json PASSED                                                        [ 16%]
tests/test_cron_parser.py::test_parse_duration_minutes PASSED                                                    [ 17%]
tests/test_cron_parser.py::test_parse_duration_hours PASSED                                                      [ 17%]
tests/test_cron_parser.py::test_parse_duration_seconds PASSED                                                    [ 17%]
tests/test_cron_parser.py::test_parse_every_day_at PASSED                                                        [ 17%]
tests/test_cron_parser.py::test_parse_every_day_at_with_minutes PASSED                                           [ 17%]
tests/test_cron_parser.py::test_parse_every_day_at_arabic PASSED                                                 [ 18%]
tests/test_cron_parser.py::test_parse_every_monday PASSED                                                        [ 18%]
tests/test_cron_parser.py::test_parse_every_weekday PASSED                                                       [ 18%]
tests/test_cron_parser.py::test_parse_iso_timestamp PASSED                                                       [ 18%]
tests/test_cron_parser.py::test_parse_cron_direct PASSED                                                         [ 18%]
tests/test_cron_parser.py::test_parse_cron_5_fields PASSED                                                       [ 19%]
tests/test_cron_parser.py::test_parse_invalid_raises PASSED                                                      [ 19%]
tests/test_cron_parser.py::test_next_run_daily PASSED                                                            [ 19%]
tests/test_cron_parser.py::test_next_run_every_30m PASSED                                                        [ 19%]
tests/test_cron_parser.py::test_next_run_one_shot_past PASSED                                                    [ 19%]
tests/test_cron_parser.py::test_next_run_one_shot_future PASSED                                                  [ 20%]
tests/test_cron_scheduler.py::test_scheduler_create_job PASSED                                                   [ 20%]
tests/test_cron_scheduler.py::test_scheduler_list_jobs PASSED                                                    [ 20%]
tests/test_cron_scheduler.py::test_scheduler_remove_job PASSED                                                   [ 20%]
tests/test_cron_scheduler.py::test_scheduler_pause_resume PASSED                                                 [ 20%]
tests/test_cron_scheduler.py::test_scheduler_start_stop PASSED                                                   [ 21%]
tests/test_cron_scheduler.py::test_scheduler_executor PASSED                                                     [ 21%]
tests/test_cron_scheduler.py::test_scheduler_max_runs PASSED                                                     [ 21%]
tests/test_cron_store.py::test_store_save_and_load PASSED                                                        [ 21%]
tests/test_cron_store.py::test_store_load_all PASSED                                                             [ 21%]
tests/test_cron_store.py::test_store_delete PASSED                                                               [ 22%]
tests/test_cron_store.py::test_store_update_status PASSED                                                        [ 22%]
tests/test_cron_store.py::test_store_count PASSED                                                                [ 22%]
tests/test_cron_store.py::test_store_load_by_status PASSED                                                       [ 22%]
tests/test_delegation.py::test_delegation_run_and_status PASSED                                                  [ 22%]
tests/test_delegation.py::test_delegation_list_agents PASSED                                                     [ 23%]
tests/test_delegation.py::test_delegation_status_not_found PASSED                                                [ 23%]
tests/test_delegation.py::test_delegation_active_count PASSED                                                    [ 23%]
tests/test_delegation.py::test_subagent_initial_state PASSED                                                     [ 23%]
tests/test_delegation.py::test_delegation_run_parallel PASSED                                                    [ 23%]
tests/test_diff_engine.py::test_generate_simple_diff PASSED                                                      [ 24%]
tests/test_diff_engine.py::test_generate_no_change PASSED                                                        [ 24%]
tests/test_diff_engine.py::test_apply_dry_run PASSED                                                             [ 24%]
tests/test_diff_engine.py::test_apply_write PASSED                                                               [ 24%]
tests/test_diff_engine.py::test_apply_conflict_detection PASSED                                                  [ 24%]
tests/test_diff_engine.py::test_apply_new_file PASSED                                                            [ 25%]
tests/test_diff_engine.py::test_stats_count PASSED                                                               [ 25%]
tests/test_diff_engine.py::test_preview PASSED                                                                   [ 25%]
tests/test_diff_engine.py::test_apply_patch_simple PASSED                                                        [ 25%]
tests/test_diff_engine.py::test_apply_patch_conflict PASSED                                                      [ 25%]
tests/test_e2e.py::test_tui_entry_point_importable PASSED                                                        [ 25%]
tests/test_e2e.py::test_api_entry_point_importable PASSED                                                        [ 26%]
tests/test_e2e.py::test_module_importable[core] PASSED                                                           [ 26%]
tests/test_e2e.py::test_module_importable[core.chat] PASSED                                                      [ 26%]
tests/test_e2e.py::test_module_importable[core.tools] PASSED                                                     [ 26%]
tests/test_e2e.py::test_module_importable[core.memory] PASSED                                                    [ 26%]
tests/test_e2e.py::test_module_importable[core.skills] PASSED                                                    [ 27%]
tests/test_e2e.py::test_module_importable[core.database] PASSED                                                  [ 27%]
tests/test_e2e.py::test_module_importable[core.session_v2] PASSED                                                [ 27%]
tests/test_e2e.py::test_module_importable[core.memory_learner] PASSED                                            [ 27%]
tests/test_e2e.py::test_module_importable[core.proxy] PASSED                                                     [ 27%]
tests/test_e2e.py::test_module_importable[core.utils] PASSED                                                     [ 28%]
tests/test_e2e.py::test_module_importable[core.workflow] PASSED                                                  [ 28%]
tests/test_e2e.py::test_module_importable[core.diagnostics] PASSED                                               [ 28%]
tests/test_e2e.py::test_module_importable[core.diff_engine] PASSED                                               [ 28%]
tests/test_e2e.py::test_module_importable[core.linter] PASSED                                                    [ 28%]
tests/test_e2e.py::test_module_importable[core.sandbox] PASSED                                                   [ 29%]
tests/test_e2e.py::test_module_importable[core.multi_editor] PASSED                                              [ 29%]
tests/test_e2e.py::test_module_importable[core.checkpoint] PASSED                                                [ 29%]
tests/test_e2e.py::test_module_importable[core.rag] PASSED                                                       [ 29%]
tests/test_e2e.py::test_module_importable[core.repo_mapper] PASSED                                               [ 29%]
tests/test_e2e.py::test_module_importable[core.vector_memory] PASSED                                             [ 30%]
tests/test_e2e.py::test_module_importable[core.session_search] PASSED                                            [ 30%]
tests/test_e2e.py::test_module_importable[core.plugin_loader] PASSED                                             [ 30%]
tests/test_e2e.py::test_module_importable[core.self_improve] PASSED                                              [ 30%]
tests/test_e2e.py::test_module_importable[core.cache] PASSED                                                     [ 30%]
tests/test_e2e.py::test_module_importable[core.auto_setup] PASSED                                                [ 31%]
tests/test_e2e.py::test_module_importable[core.project_tracker] PASSED                                           [ 31%]
tests/test_e2e.py::test_module_importable[core.project_context] PASSED                                           [ 31%]
tests/test_e2e.py::test_module_importable[core.project_structure] PASSED                                         [ 31%]
tests/test_e2e.py::test_module_importable[core.token_budget] PASSED                                              [ 31%]
tests/test_e2e.py::test_module_importable[core.self_reflection] PASSED                                           [ 32%]
tests/test_e2e.py::test_module_importable[core.suggester] PASSED                                                 [ 32%]
tests/test_e2e.py::test_module_importable[core.providers] PASSED                                                 [ 32%]
tests/test_e2e.py::test_module_importable[core.providers.providers] PASSED                                       [ 32%]
tests/test_e2e.py::test_module_importable[core.providers.gguf] PASSED                                            [ 32%]
tests/test_e2e.py::test_module_importable[core.config] PASSED                                                    [ 33%]
tests/test_e2e.py::test_module_importable[core.config.settings] PASSED                                           [ 33%]
tests/test_e2e.py::test_module_importable[core.config.keychain] PASSED                                           [ 33%]
tests/test_e2e.py::test_module_importable[core.uil] PASSED                                                       [ 33%]
tests/test_e2e.py::test_module_importable[core.uil.contract] PASSED                                              [ 33%]
tests/test_e2e.py::test_module_importable[core.uil.analyzer] PASSED                                              [ 34%]
tests/test_e2e.py::test_module_importable[core.uil.router] PASSED                                                [ 34%]
tests/test_e2e.py::test_module_importable[core.uil.planner] PASSED                                               [ 34%]
tests/test_e2e.py::test_module_importable[core.uil.brain] PASSED                                                 [ 34%]
tests/test_e2e.py::test_module_importable[core.uil.knowledge] PASSED                                             [ 34%]
tests/test_e2e.py::test_module_importable[core.mcp] PASSED                                                       [ 35%]
tests/test_e2e.py::test_module_importable[core.mcp.client] PASSED                                                [ 35%]
tests/test_e2e.py::test_module_importable[core.project] PASSED                                                   [ 35%]
tests/test_e2e.py::test_module_importable[core.project.state] PASSED                                             [ 35%]
tests/test_e2e.py::test_module_importable[core.project.scanner] PASSED                                           [ 35%]
tests/test_e2e.py::test_module_importable[core.project.git] PASSED                                               [ 36%]
tests/test_e2e.py::test_module_importable[core.project.manifest] PASSED                                          [ 36%]
tests/test_e2e.py::test_module_importable[core.agents] PASSED                                                    [ 36%]
tests/test_e2e.py::test_module_importable[core.agents.agent] PASSED                                              [ 36%]
tests/test_e2e.py::test_module_importable[core.agents.expert] PASSED                                             [ 36%]
tests/test_e2e.py::test_module_importable[cli] PASSED                                                            [ 37%]
tests/test_e2e.py::test_module_importable[cli.app] PASSED                                                        [ 37%]
tests/test_e2e.py::test_module_importable[cli.commands] PASSED                                                   [ 37%]
tests/test_e2e.py::test_module_importable[cli.display] PASSED                                                    [ 37%]
tests/test_e2e.py::test_module_importable[cli.input] PASSED                                                      [ 37%]
tests/test_e2e.py::test_module_importable[cli.theme] PASSED                                                      [ 37%]
tests/test_e2e.py::test_module_importable[tui] PASSED                                                            [ 38%]
tests/test_e2e.py::test_module_importable[tui.app] PASSED                                                        [ 38%]
tests/test_e2e.py::test_module_importable[tui.chat_engine] PASSED                                                [ 38%]
tests/test_e2e.py::test_module_importable[tui.commands] PASSED                                                   [ 38%]
tests/test_e2e.py::test_module_importable[tui.state] PASSED                                                      [ 38%]
tests/test_e2e.py::test_module_importable[tui.widgets] PASSED                                                    [ 39%]
tests/test_e2e.py::test_module_importable[tui.widgets.header] PASSED                                             [ 39%]
tests/test_e2e.py::test_module_importable[tui.screens] PASSED                                                    [ 39%]
tests/test_e2e.py::test_module_importable[tui.screens.help] PASSED                                               [ 39%]
tests/test_e2e.py::test_module_importable[tui.screens.settings] PASSED                                           [ 39%]
tests/test_e2e.py::test_module_importable[tui.screens.session_crud] PASSED                                       [ 40%]
tests/test_e2e.py::test_module_importable[tui.screens.memory_crud] PASSED                                        [ 40%]
tests/test_e2e.py::test_module_importable[tui.screens.detail] PASSED                                             [ 40%]
tests/test_e2e.py::test_module_importable[tui.screens.tool_detail] PASSED                                        [ 40%]
tests/test_e2e.py::test_module_importable[tui.screens.ubuntu_grid] PASSED                                        [ 40%]
tests/test_e2e.py::test_module_importable[scripts] PASSED                                                        [ 41%]
tests/test_e2e.py::test_module_importable[scripts.api_server] PASSED                                             [ 41%]
tests/test_e2e.py::test_module_importable[scripts.run_textual] PASSED                                            [ 41%]
tests/test_e2e.py::test_module_importable[scripts.web_app] PASSED                                                [ 41%]
tests/test_e2e.py::test_create_provider_from_config PASSED                                                       [ 41%]
tests/test_e2e.py::test_provider_has_model_listing PASSED                                                        [ 42%]
tests/test_e2e.py::test_tool_definitions_have_required_fields PASSED                                             [ 42%]
tests/test_e2e.py::test_tool_execute_read PASSED                                                                 [ 42%]
tests/test_e2e.py::test_tool_execute_bash_echo PASSED                                                            [ 42%]
tests/test_e2e.py::test_memory_store_crud PASSED                                                                 [ 42%]
tests/test_e2e.py::test_session_v2_create_save_search PASSED                                                     [ 43%]
tests/test_e2e.py::test_v2_modules_emit_deprecation_warning PASSED                                               [ 43%]
tests/test_e2e.py::test_dual_session_persistence PASSED                                                          [ 43%]
tests/test_e2e.py::test_no_wildcard_imports_in_cli PASSED                                                        [ 43%]
tests/test_engines_e2e.py::TestIntelligenceClassifier::test_classify_code_write PASSED                           [ 43%]
tests/test_engines_e2e.py::TestIntelligenceClassifier::test_classify_code_modify PASSED                          [ 44%]
tests/test_engines_e2e.py::TestIntelligenceClassifier::test_classify_code_review PASSED                          [ 44%]
tests/test_engines_e2e.py::TestIntelligenceClassifier::test_classify_research PASSED                             [ 44%]
tests/test_engines_e2e.py::TestIntelligenceClassifier::test_classify_chat PASSED                                 [ 44%]
tests/test_engines_e2e.py::TestIntelligenceClassifier::test_classify_empty_input PASSED                          [ 44%]
tests/test_engines_e2e.py::TestIntelligenceClassifier::test_detected_features PASSED                             [ 45%]
tests/test_engines_e2e.py::TestIntelligenceClassifier::test_detected_languages PASSED                            [ 45%]
tests/test_engines_e2e.py::TestIntelligenceClassifier::test_embedding_method_used PASSED                         [ 45%]
tests/test_engines_e2e.py::TestIntelligencePlanner::test_plan_code_write_uses_pattern PASSED                     [ 45%]
tests/test_engines_e2e.py::TestIntelligencePlanner::test_plan_code_review_has_steps PASSED                       [ 45%]
tests/test_engines_e2e.py::TestIntelligencePlanner::test_plan_chat_is_minimal PASSED                             [ 46%]
tests/test_engines_e2e.py::TestIntelligencePlanner::test_patterns_count PASSED                                   [ 46%]
tests/test_engines_e2e.py::TestValidationRunner::test_runs_valid_python PASSED                                   [ 46%]
tests/test_engines_e2e.py::TestValidationRunner::test_catches_runtime_error PASSED                               [ 46%]
tests/test_engines_e2e.py::TestValidationRunner::test_catches_syntax_error PASSED                                [ 46%]
tests/test_engines_e2e.py::TestValidationRunner::test_timeout_on_infinite_loop PASSED                            [ 47%]
tests/test_engines_e2e.py::TestValidationRunner::test_import_check PASSED                                        [ 47%]
tests/test_engines_e2e.py::TestValidationRunner::test_import_check_catches_error PASSED                          [ 47%]
tests/test_engines_e2e.py::TestValidationReporter::test_good_code_scores_high PASSED                             [ 47%]
tests/test_engines_e2e.py::TestValidationReporter::test_bad_code_scores_lower PASSED                             [ 47%]
tests/test_engines_e2e.py::TestValidationReporter::test_empty_output_detected PASSED                             [ 48%]
tests/test_engines_e2e.py::TestValidationReporter::test_finds_placeholder_content PASSED                         [ 48%]
tests/test_engines_e2e.py::TestIsolationPolicy::test_blocks_rm_rf PASSED                                         [ 48%]
tests/test_engines_e2e.py::TestIsolationPolicy::test_blocks_chmod_777 PASSED                                     [ 48%]
tests/test_engines_e2e.py::TestIsolationPolicy::test_blocks_curl_pipe_bash PASSED                                [ 48%]
tests/test_engines_e2e.py::TestIsolationPolicy::test_allows_safe_commands PASSED                                 [ 49%]
tests/test_engines_e2e.py::TestIsolationPolicy::test_level_0_allows_read_blocks_write PASSED                     [ 49%]
tests/test_engines_e2e.py::TestIsolationPolicy::test_level_3_allows_all PASSED                                   [ 49%]
tests/test_engines_e2e.py::TestIsolationPolicy::test_profiles_exist PASSED                                       [ 49%]
tests/test_engines_e2e.py::TestAdapters::test_adapt_classification PASSED                                        [ 49%]
tests/test_engines_e2e.py::TestAdapters::test_adapt_plan PASSED                                                  [ 50%]
tests/test_engines_e2e.py::TestFeatureFlags::test_all_on_by_default PASSED                                       [ 50%]
tests/test_engines_e2e.py::TestFeatureFlags::test_on_with_missing_engines_key PASSED                             [ 50%]
tests/test_engines_e2e.py::TestFeatureFlags::test_can_disable_individual_engine PASSED                           [ 50%]
tests/test_engines_e2e.py::TestFeatureFlags::test_all_off_explicitly PASSED                                      [ 50%]
tests/test_engines_e2e.py::TestFeatureFlags::test_summary_string PASSED                                          [ 50%]
tests/test_engines_e2e.py::TestFeatureFlags::test_summary_no_config PASSED                                       [ 51%]
tests/test_engines_e2e.py::TestTrustTracker::test_starts_at_zero PASSED                                          [ 51%]
tests/test_engines_e2e.py::TestTrustTracker::test_records_agreement PASSED                                       [ 51%]
tests/test_engines_e2e.py::TestTrustTracker::test_not_promoted_with_few_comparisons PASSED                       [ 51%]
tests/test_engines_e2e.py::TestTrustTracker::test_persistence PASSED                                             [ 51%]
tests/test_engines_e2e.py::TestBrainEngineIntegration::test_validation_merge_recompute PASSED                    [ 52%]
tests/test_engines_e2e.py::TestBrainEngineIntegration::test_recompute_clears PASSED                              [ 52%]
tests/test_engines_e2e.py::TestBrainEngineIntegration::test_engine_enabled_true_by_default PASSED                [ 52%]
tests/test_engines_e2e.py::TestBrainEngineIntegration::test_classifier_new_examples_200_plus PASSED              [ 52%]
tests/test_engines_e2e.py::TestBrainEngineIntegration::test_classifier_new_reasoning_type PASSED                 [ 52%]
tests/test_engines_e2e.py::TestBrainEngineIntegration::test_classifier_complex_type PASSED                       [ 53%]
tests/test_engines_e2e.py::TestBrainEngineIntegration::test_classifier_complex_needs_2_plus_keywords PASSED      [ 53%]
tests/test_engines_e2e.py::TestBrainEngineIntegration::test_keyword_rules_include_reasoning PASSED               [ 53%]
tests/test_executor_adapter.py::TestSimpleChatExecutor::test_returns_execution_result PASSED                     [ 53%]
tests/test_executor_adapter.py::TestSimpleChatExecutor::test_success_on_normal_reply PASSED                      [ 53%]
tests/test_executor_adapter.py::TestSimpleChatExecutor::test_failure_on_provider_error PASSED                    [ 54%]
tests/test_executor_adapter.py::TestSimpleChatExecutor::test_injects_plan_when_decomposed PASSED                 [ 54%]
tests/test_executor_adapter.py::TestSimpleChatExecutor::test_no_provider_raises_clear_error PASSED               [ 54%]
tests/test_executor_adapter.py::TestAutonomousExecutor::test_returns_execution_result PASSED                     [ 54%]
tests/test_executor_adapter.py::TestAutonomousExecutor::test_success_when_agent_completes PASSED                 [ 54%]
tests/test_executor_adapter.py::TestAutonomousExecutor::test_injects_plan_when_available PASSED                  [ 55%]
tests/test_executor_adapter.py::TestAutonomousExecutor::test_no_provider_raises_clear_error PASSED               [ 55%]
tests/test_executor_adapter.py::TestExpertTeamExecutor::test_returns_execution_result PASSED                     [ 55%]
tests/test_executor_adapter.py::TestExpertTeamExecutor::test_summary_is_non_empty_string PASSED                  [ 55%]
tests/test_executor_adapter.py::TestDirectToolExecutor::test_returns_execution_result PASSED                     [ 55%]
tests/test_executor_adapter.py::TestDirectToolExecutor::test_handles_empty_tool_defs PASSED                      [ 56%]
tests/test_executor_adapter.py::TestExecutorMap::test_covers_all_modes PASSED                                    [ 56%]
tests/test_executor_adapter.py::TestExecutorMap::test_each_is_callable PASSED                                    [ 56%]
tests/test_executor_adapter.py::TestExecutorMap::test_each_returns_execution_result PASSED                       [ 56%]
tests/test_executor_adapter.py::TestEdgeCases::test_empty_user_input PASSED                                      [ 56%]
tests/test_executor_adapter.py::TestEdgeCases::test_very_long_user_input PASSED                                  [ 57%]
tests/test_executor_adapter.py::TestEdgeCases::test_state_mutations_visible_to_caller PASSED                     [ 57%]
tests/test_features.py::test_git_auto_commit_and_undo PASSED                                                     [ 57%]
tests/test_features.py::test_project_config PASSED                                                               [ 57%]
tests/test_features.py::test_load_command PASSED                                                                 [ 57%]
tests/test_features.py::test_auto_summary PASSED                                                                 [ 58%]
tests/test_features.py::test_expert_profile_structure PASSED                                                     [ 58%]
tests/test_features.py::test_build_index_with_extra_ignore PASSED                                                [ 58%]
tests/test_guard.py::test_safe_command PASSED                                                                    [ 58%]
tests/test_guard.py::test_block_rm_rf_root PASSED                                                                [ 58%]
tests/test_guard.py::test_block_rm_rf_home PASSED                                                                [ 59%]
tests/test_guard.py::test_block_fork_bomb PASSED                                                                 [ 59%]
tests/test_guard.py::test_warn_rm_rf_project PASSED                                                              [ 59%]
tests/test_guard.py::test_warn_git_hard_reset PASSED                                                             [ 59%]
tests/test_guard.py::test_warn_drop_table PASSED                                                                 [ 59%]
tests/test_guard.py::test_warn_curl_pipe_bash PASSED                                                             [ 60%]
tests/test_guard.py::test_force_override PASSED                                                                  [ 60%]
tests/test_guard.py::test_normal_git_commands PASSED                                                             [ 60%]
tests/test_guard.py::test_block_device_redirect PASSED                                                           [ 60%]
tests/test_guard.py::test_guard_instance_with_cwd PASSED                                                         [ 60%]
tests/test_guard.py::test_sanitized_command_preserved PASSED                                                     [ 61%]
tests/test_integration.py::test_integration_workflow PASSED                                                      [ 61%]
tests/test_linter.py::test_linter_creates PASSED                                                                 [ 61%]
tests/test_linter.py::test_detect_language_python PASSED                                                         [ 61%]
tests/test_linter.py::test_detect_language_js PASSED                                                             [ 61%]
tests/test_linter.py::test_detect_language_unknown PASSED                                                        [ 62%]
tests/test_linter.py::test_lint_python_file PASSED                                                               [ 62%]
tests/test_linter.py::test_lint_missing_file PASSED                                                              [ 62%]
tests/test_linter.py::test_lint_result_format PASSED                                                             [ 62%]
tests/test_linter.py::test_lint_result_ok PASSED                                                                 [ 62%]
tests/test_multi_editor.py::test_editor_creates PASSED                                                           [ 62%]
tests/test_multi_editor.py::test_add_and_preview PASSED                                                          [ 63%]
tests/test_multi_editor.py::test_remove PASSED                                                                   [ 63%]
tests/test_multi_editor.py::test_commit_dry_run PASSED                                                           [ 63%]
tests/test_multi_editor.py::test_commit_write PASSED                                                             [ 63%]
tests/test_multi_editor.py::test_clear PASSED                                                                    [ 63%]
tests/test_multi_editor.py::test_singleton PASSED                                                                [ 64%]
tests/test_plugin_loader.py::test_watcher_snapshot PASSED                                                        [ 64%]
tests/test_plugin_loader.py::test_watcher_detect_added PASSED                                                    [ 64%]
tests/test_plugin_loader.py::test_watcher_detect_modified PASSED                                                 [ 64%]
tests/test_plugin_loader.py::test_watcher_detect_removed PASSED                                                  [ 64%]
tests/test_plugin_loader.py::test_watcher_start_stop PASSED                                                      [ 65%]
tests/test_plugin_loader.py::test_hot_reloader_stats PASSED                                                      [ 65%]
tests/test_plugin_loader.py::test_hot_reloader_reload_all PASSED                                                 [ 65%]
tests/test_plugin_loader.py::test_get_hot_reloader_singleton PASSED                                              [ 65%]
tests/test_project_context.py::test_project_context PASSED                                                       [ 65%]
tests/test_project_context.py::test_project_structure PASSED                                                     [ 66%]
tests/test_project_context.py::test_file_search PASSED                                                           [ 66%]
tests/test_providers.py::TestCreateProvider::test_opencode_zen PASSED                                            [ 66%]
tests/test_providers.py::TestCreateProvider::test_ollama PASSED                                                  [ 66%]
tests/test_providers.py::TestCreateProvider::test_openai PASSED                                                  [ 66%]
tests/test_providers.py::TestCreateProvider::test_deepseek PASSED                                                [ 67%]
tests/test_providers.py::TestResolveModel::test_explicit_model PASSED                                            [ 67%]
tests/test_providers.py::TestResolveModel::test_empty_model_has_default PASSED                                   [ 67%]
tests/test_providers.py::TestGetAvailableModels::test_returns_list PASSED                                        [ 67%]
tests/test_providers.py::TestFetchFreeModels::test_returns_list PASSED                                           [ 67%]
tests/test_providers.py::TestFetchFreeModels::test_contains_expected_models PASSED                               [ 68%]
tests/test_providers.py::TestOllamaModels::test_returns_empty_when_not_running PASSED                            [ 68%]
tests/test_providers.py::TestProviderConfig::test_custom_base_url PASSED                                         [ 68%]
tests/test_providers.py::TestProviderConfig::test_deepseek_model PASSED                                          [ 68%]
tests/test_providers.py::TestProviderConfig::test_ollama_with_explicit_url PASSED                                [ 68%]
tests/test_rag.py::test_rag_add_search PASSED                                                                    [ 69%]
tests/test_rag.py::test_rag_count PASSED                                                                         [ 69%]
tests/test_rag.py::test_rag_empty_search PASSED                                                                  [ 69%]
tests/test_rag.py::test_rag_singleton PASSED                                                                     [ 69%]
tests/test_rag.py::test_cosine_math PASSED                                                                       [ 69%]
tests/test_repo_mapper.py::test_repo_mapper_scan_current PASSED                                                  [ 70%]
tests/test_repo_mapper.py::test_repo_mapper_stats PASSED                                                         [ 70%]
tests/test_repo_mapper.py::test_repo_mapper_select PASSED                                                        [ 70%]
tests/test_repo_mapper.py::test_repo_mapper_find_file PASSED                                                     [ 70%]
tests/test_repo_mapper.py::test_repo_mapper_dependencies PASSED                                                  [ 70%]
tests/test_repo_mapper.py::test_repo_mapper_cache PASSED                                                         [ 71%]
tests/test_repo_mapper.py::test_file_node_symbols PASSED                                                         [ 71%]
tests/test_repo_mapper.py::test_repo_mapper_scan_empty_dir PASSED                                                [ 71%]
tests/test_sandbox.py::test_sandbox_result_ok PASSED                                                             [ 71%]
tests/test_sandbox.py::test_sandbox_result_timeout PASSED                                                        [ 71%]
tests/test_sandbox.py::test_execute_simple_echo FAILED                                                           [ 72%]
tests/test_sandbox.py::test_execute_exit_code PASSED                                                             [ 72%]
tests/test_sandbox.py::test_execute_nonexistent_command PASSED                                                   [ 72%]
tests/test_sandbox.py::test_detect_mode PASSED                                                                   [ 72%]
tests/test_sandbox.py::test_resource_limits_default PASSED                                                       [ 72%]
tests/test_sandbox.py::test_singleton_exists PASSED                                                              [ 73%]
tests/test_session_search.py::test_snippet_exact_match PASSED                                                    [ 73%]
tests/test_session_search.py::test_snippet_no_match PASSED                                                       [ 73%]
tests/test_session_search.py::test_snippet_short_text PASSED                                                     [ 73%]
tests/test_session_search.py::test_searcher_init PASSED                                                          [ 73%]
tests/test_session_search.py::test_searcher_search_empty_query PASSED                                            [ 74%]
tests/test_session_search.py::test_searcher_search_by_name PASSED                                                [ 74%]
tests/test_session_search.py::test_searcher_list_recent PASSED                                                   [ 74%]
tests/test_session_search.py::test_searcher_rebuild_index PASSED                                                 [ 74%]
tests/test_session_search.py::test_searcher_get_session_context_missing PASSED                                   [ 74%]
tests/test_session_search.py::test_fts_sanitize PASSED                                                           [ 75%]
tests/test_session_search.py::test_end_to_end_search PASSED                                                      [ 75%]
tests/test_token_budget.py::test_budget_creates PASSED                                                           [ 75%]
tests/test_token_budget.py::test_budget_consume_free_model PASSED                                                [ 75%]
tests/test_token_budget.py::test_budget_consume_paid_model PASSED                                                [ 75%]
tests/test_token_budget.py::test_budget_would_exceed PASSED                                                      [ 75%]
tests/test_token_budget.py::test_budget_exceeded_raises PASSED                                                   [ 76%]
tests/test_token_budget.py::test_budget_remaining PASSED                                                         [ 76%]
tests/test_token_budget.py::test_budget_summary PASSED                                                           [ 76%]
tests/test_token_budget.py::test_get_pricing_known PASSED                                                        [ 76%]
tests/test_token_budget.py::test_get_pricing_unknown PASSED                                                      [ 76%]
tests/test_token_budget.py::test_singleton_budget PASSED                                                         [ 77%]
tests/test_tui.py::test_app_creation PASSED                                                                      [ 77%]
tests/test_tui.py::test_main_screen_creation PASSED                                                              [ 77%]
tests/test_tui.py::test_state_creation PASSED                                                                    [ 77%]
tests/test_tui.py::test_chat_engine_creation PASSED                                                              [ 77%]
tests/test_tui.py::test_command_handler PASSED                                                                   [ 78%]
tests/test_tui.py::test_app_headless_mount PASSED                                                                [ 78%]
tests/test_tui.py::test_main_widgets_present PASSED                                                              [ 78%]
tests/test_tui.py::test_input_focus_on_start PASSED                                                              [ 78%]
tests/test_tui.py::test_ctrl_l_clears_chat PASSED                                                                [ 78%]
tests/test_tui.py::test_ctrl_t_toggles_thinking PASSED                                                           [ 79%]
tests/test_tui.py::test_ctrl_p_pushes_help PASSED                                                                [ 79%]
tests/test_tui.py::test_escape_dismisses_modals PASSED                                                           [ 79%]
tests/test_tui.py::test_help_screen_mounts PASSED                                                                                                                                                         [ 79%]
tests/test_tui.py::test_settings_screen_mounts SKIPPED (SettingsScreen reads global config.json — can conflict
with other test state)                                                                                                                                                                                    [ 79%]
tests/test_tui.py::test_session_list_screen_mounts PASSED                                                                                                                                                 [ 80%]
tests/test_tui.py::test_memory_list_screen_mounts PASSED                                                                                                                                                  [ 80%]
tests/test_tui.py::test_ubuntu_grid_mounts PASSED                                                                                                                                                         [ 80%]
tests/test_tui.py::test_tool_detail_screen_mounts PASSED                                                                                                                                                  [ 80%]
tests/test_tui.py::test_text_detail_screen_mounts PASSED                                                                                                                                                  [ 80%]
tests/test_tui.py::test_slash_help_command PASSED                                                                                                                                                         [ 81%]
tests/test_tui.py::test_slash_clear_command PASSED                                                                                                                                                        [ 81%]
tests/test_tui.py::test_slash_doctor_command PASSED                                                                                                                                                       [ 81%]
tests/test_tui.py::test_state_save_and_load_session PASSED                                                                                                                                                [ 81%]
tests/test_tui.py::test_tool_defs_include_all_sources PASSED                                                                                                                                              [ 81%]
tests/test_uil_knowledge.py::test_knowledge_record_and_query PASSED                                                                                                                                       [ 82%]
tests/test_uil_knowledge.py::test_knowledge_brain_auto_records PASSED                                                                                                                                     [ 82%]
tests/test_uil_knowledge.py::test_knowledge_five_executions_answer_avg_time PASSED                                                                                                                        [ 82%]
tests/test_uil_knowledge.py::test_knowledge_suggest_insufficient_data PASSED                                                                                                                              [ 82%]
tests/test_uil_knowledge.py::test_knowledge_suggest_expert_team_after_failures PASSED                                                                                                                     [ 82%]
tests/test_uil_knowledge.py::test_knowledge_suggest_autonomous_for_slow PASSED                                                                                                                            [ 83%]
tests/test_uil_knowledge.py::test_router_knowledge_mode_override PASSED                                                                                                                                   [ 83%]
tests/test_uil_knowledge.py::test_router_knowledge_backward_compat PASSED                                                                                                                                 [ 83%]
tests/test_uil_knowledge.py::test_knowledge_suggest_expert_team_after_verify_failures PASSED                                                                                                              [ 83%]
tests/test_uil_knowledge.py::test_direct_tool_executor_prefers_bash PASSED                                                                                                                                [ 83%]
tests/test_uil_p12.py::test_mode_selection PASSED                                                                                                                                                         [ 84%]
tests/test_uil_p12.py::test_tool_filtering PASSED                                                                                                                                                         [ 84%]
tests/test_uil_p12.py::test_decision_path PASSED                                                                                                                                                          [ 84%]
tests/test_uil_p12.py::test_plan_defaults PASSED                                                                                                                                                          [ 84%]
tests/test_uil_p12.py::test_direct_tool PASSED                                                                                                                                                            [ 84%]
tests/test_uil_p12.py::test_brain_orchestrates_analyze_route PASSED                                                                                                                                       [ 85%]
tests/test_uil_p12.py::test_brain_no_classification_logic PASSED                                                                                                                                          [ 85%]
tests/test_uil_p12.py::test_brain_no_tool_selection_logic PASSED                                                                                                                                          [ 85%]
tests/test_uil_p12.py::test_brain_with_custom_executor PASSED                                                                                                                                             [ 85%]
tests/test_uil_p12.py::test_brain_default_executor_stub PASSED                                                                                                                                            [ 85%]
tests/test_uil_p12.py::test_brain_full_end_to_end PASSED                                                                                                                                                  [ 86%]
tests/test_uil_p13.py::test_main_imports_uil PASSED                                                                                                                                                       [ 86%]
tests/test_uil_p13.py::test_uil_process_with_simple_chat_executor PASSED                                                                                                                                  [ 86%]
tests/test_uil_p13.py::test_uil_process_with_all_executors PASSED                                                                                                                                         [ 86%]
tests/test_uil_p13.py::test_uil_process_passes_messages PASSED                                                                                                                                            [ 86%]
tests/test_uil_p13.py::test_uil_process_with_tool_defs_update PASSED                                                                                                                                      [ 87%]
tests/test_uil_p13.py::test_uil_no_global_expert_team_import PASSED                                                                                                                                       [ 87%]
tests/test_uil_p13.py::test_main_py_uses_uil_not_expert_team PASSED                                                                                                                                       [ 87%]
tests/test_uil_p15.py::test_feedback_string_wrapping PASSED                                                                                                                                               [ 87%]
tests/test_uil_p15.py::test_feedback_rich_passthrough PASSED                                                                                                                                              [ 87%]
tests/test_uil_p15.py::test_feedback_steps_planned_with_planner PASSED                                                                                                                                    [ 87%]
tests/test_uil_p15.py::test_plan_consumption_context_carries_plan PASSED                                                                                                                                  [ 88%]
tests/test_uil_p15.py::test_plan_consumption_no_planner PASSED                                                                                                                                            [ 88%]
tests/test_uil_p15.py::test_delegation_all_routing_decision_fields PASSED                                                                                                                                 [ 88%]
tests/test_uil_p15.py::test_delegation_existing_executor_unchanged PASSED                                                                                                                                 [ 88%]
tests/test_uil_planner.py::test_planner_complex PASSED                                                                                                                                                    [ 88%]
tests/test_uil_planner.py::test_planner_code_write PASSED                                                                                                                                                 [ 89%]
tests/test_uil_planner.py::test_planner_code_modify PASSED                                                                                                                                                [ 89%]
tests/test_uil_planner.py::test_planner_minimal_code_review PASSED                                                                                                                                        [ 89%]
tests/test_uil_planner.py::test_planner_minimal_chat PASSED                                                                                                                                               [ 89%]
tests/test_uil_planner.py::test_planner_minimal_research PASSED                                                                                                                                           [ 89%]
tests/test_uil_planner.py::test_planner_minimal_browser PASSED                                                                                                                                            [ 90%]
tests/test_uil_planner.py::test_planner_minimal_database PASSED                                                                                                                                           [ 90%]
tests/test_uil_planner.py::test_planner_minimal_file_ops PASSED                                                                                                                                           [ 90%]
tests/test_uil_planner.py::test_planner_minimal_unknown PASSED                                                                                                                                            [ 90%]
tests/test_uil_planner.py::test_planner_traceability PASSED                                                                                                                                               [ 90%]
tests/test_uil_planner.py::test_planner_always_active PASSED                                                                                                                                              [ 91%]
tests/test_uil_planner.py::test_planner_selective_in_brain PASSED                                                                                                                                         [ 91%]
tests/test_vector_memory.py::test_tfidf_tokenize PASSED                                                                                                                                                   [ 91%]
tests/test_vector_memory.py::test_tfidf_encode PASSED                                                                                                                                                     [ 91%]
tests/test_vector_memory.py::test_tfidf_cosine PASSED                                                                                                                                                     [ 91%]
tests/test_vector_memory.py::test_tfidf_cosine_unrelated PASSED                                                                                                                                           [ 92%]
tests/test_vector_memory.py::test_vector_store_add_search_tfidf PASSED                                                                                                                                    [ 92%]
tests/test_vector_memory.py::test_vector_store_search_unrelated PASSED                                                                                                                                    [ 92%]
tests/test_vector_memory.py::test_vector_store_tag_search PASSED                                                                                                                                          [ 92%]
tests/test_vector_memory.py::test_vector_store_get_delete PASSED                                                                                                                                          [ 92%]
tests/test_vector_memory.py::test_vector_store_update PASSED                                                                                                                                              [ 93%]
tests/test_vector_memory.py::test_vector_store_list_count PASSED                                                                                                                                          [ 93%]
tests/test_vector_memory.py::test_ollama_similarity_math PASSED                                                                                                                                           [ 93%]
tests/test_verifier.py::TestHtmlVerifierHiddenElement::test_detects_critical PASSED                                                                                                                       [ 93%]
tests/test_verifier.py::TestHtmlVerifierHiddenElement::test_clean_has_no_critical PASSED                                                                                                                  [ 93%]
tests/test_verifier.py::TestHtmlVerifierTagBalance::test_detects_unbalanced_div PASSED                                                                                                                    [ 94%]
tests/test_verifier.py::TestHtmlVerifierTagBalance::test_unclosed_style PASSED                                                                                                                            [ 94%]
tests/test_verifier.py::TestHtmlVerifierI18n::test_detects_missing_keys PASSED                                                                                                                            [ 94%]
tests/test_verifier.py::TestHtmlVerifierOnclick::test_detects_missing_handler PASSED                                                                                                                      [ 94%]
tests/test_verifier.py::TestHtmlVerifierCleanPage::test_clean_passes_all PASSED                                                                                                                           [ 94%]
tests/test_verifier.py::TestHtmlVerifierCleanPage::test_empty_html_info PASSED                                                                                                                            [ 95%]
tests/test_verifier.py::TestCodeVerifier::test_unbalanced_braces PASSED                                                                                                                                   [ 95%]
tests/test_verifier.py::TestCodeVerifier::test_unbalanced_parentheses PASSED                                                                                                                              [ 95%]
tests/test_verifier.py::TestCodeVerifier::test_balanced_passes PASSED                                                                                                                                     [ 95%]
tests/test_verifier.py::TestBashVerifierDangerous::test_rm_rf_root PASSED                                                                                                                                 [ 95%]
tests/test_verifier.py::TestBashVerifierDangerous::test_piped_curl_bash PASSED                                                                                                                            [ 96%]
tests/test_verifier.py::TestBashVerifierDangerous::test_fork_bomb PASSED                                                                                                                                  [ 96%]
tests/test_verifier.py::TestBashVerifierDangerous::test_safe_passes PASSED                                                                                                                                [ 96%]
tests/test_verifier.py::TestBashVerifierQuotes::test_unclosed_single_quote PASSED                                                                                                                         [ 96%]
tests/test_verifier.py::TestBashVerifierQuotes::test_closed_quotes_pass PASSED                                                                                                                            [ 96%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.CODE_WRITE-html] PASSED                                                                                                      [ 97%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.COMPLEX-html] PASSED                                                                                                         [ 97%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.BROWSER-html] PASSED                                                                                                         [ 97%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.CODE_MODIFY-code] PASSED                                                                                                     [ 97%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.CODE_READ-code] PASSED                                                                                                       [ 97%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.CODE_REVIEW-code] PASSED                                                                                                     [ 98%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.SYSTEM-bash] PASSED                                                                                                          [ 98%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.CHAT-generic] PASSED                                                                                                         [ 98%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.RESEARCH-generic] PASSED                                                                                                     [ 98%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.DATABASE-generic] PASSED                                                                                                     [ 98%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.REASONING-generic] PASSED                                                                                                    [ 99%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.FILE_OPS-generic] PASSED                                                                                                     [ 99%]
tests/test_verifier.py::TestVerifierRegistry::test_correct_verifier[TaskType.UNKNOWN-generic] PASSED                                                                                                      [ 99%]
tests/test_verifier.py::TestVerifierRegistry::test_none_returns_generic PASSED                                                                                                                            [ 99%]
tests/test_verifier.py::TestBrainVerifierIntegration::test_brain_detects_critical FAILED                                                                                                                  [ 99%]
tests/test_verifier.py::TestBrainVerifierIntegration::test_brain_passes_clean FAILED                                                                                                                      [100%]

=================================================================================================== FAILURES ===================================================================================================
________________________________________________________________________________________ test_background_run_and_status ________________________________________________________________________________________
tests\test_background.py:16: in test_background_run_and_status
    assert task.status == TaskStatus.DONE
E   assert <TaskStatus.FAILED: 'failed'> == <TaskStatus.DONE: 'done'>
E    +  where <TaskStatus.FAILED: 'failed'> = BackgroundTask(id='task_85fe2b7c', prompt='echo hello', status=<TaskStatus.FAILED: 'failed'>, result='', error="Command not found: echo hello. Use 'bash -c' or 'cmd /c' explicitly if shell features are needed.", created_at='2026-06-26T08:39:07.906842+00:00', started_at='2026-06-26T08:39:07.906842+00:00', finished_at='2026-06-26T08:39:07.925273+00:00', elapsed_seconds=0.017858300008811057, thread=<Thread(bg-task_85fe2b7c, stopped daemon 16184)>).status
E    +  and   <TaskStatus.DONE: 'done'> = TaskStatus.DONE
---------------------------------------------------------------------------------------------- Captured log call -----------------------------------------------------------------------------------------------
WARNING  widdx.sandbox:sandbox.py:657 Command not found (shell=False): echo hello
___________________________________________________________________________________________ test_execute_simple_echo ___________________________________________________________________________________________
tests\test_sandbox.py:22: in test_execute_simple_echo
    assert result.ok
E   assert False
E    +  where False = SandboxResult(stdout='', stderr="Command not found: echo hello. Use 'bash -c' or 'cmd /c' explicitly if shell features are needed.", exit_code=127, was_timeout=False, was_killed=False, elapsed_ms=8.482399993226863, mode='subprocess', files_created=[], files_modified=[]).ok
---------------------------------------------------------------------------------------------- Captured log call -----------------------------------------------------------------------------------------------
WARNING  widdx.sandbox:sandbox.py:657 Command not found (shell=False): echo hello
___________________________________________________________________________ TestBrainVerifierIntegration.test_brain_detects_critical ___________________________________________________________________________
tests\test_verifier.py:296: in test_brain_detects_critical
    assert verifier in ("html", "generic"), f"Expected html or generic, got {verifier}"
E   AssertionError: Expected html or generic, got none
E   assert 'none' in ('html', 'generic')
_____________________________________________________________________________ TestBrainVerifierIntegration.test_brain_passes_clean _____________________________________________________________________________
tests\test_verifier.py:317: in test_brain_passes_clean
    assert crits == 0, f"Expected 0 criticals, got {crits}"
E   AssertionError: Expected 0 criticals, got 999
E   assert 999 == 0
=========================================================================================== short test summary info ============================================================================================
FAILED tests/test_background.py::test_background_run_and_status - assert <TaskStatus.FAILED: 'failed'> == <TaskStatus.DONE: 'done'>
 +  where <TaskStatus.FAILED: 'failed'> = BackgroundTask(id='task_85fe2b7c', prompt='echo hello', status=<TaskStatus.FAILED: 'failed'>, result='', error="Command not found: echo hello. Use 'bash -c' or 'cmd /c' explicitly if shell features are needed.", created_at='2026-06-26T08:39:07.906842+00:00', started_at='2026-06-26T08:39:07.906842+00:00', finished_at='2026-06-26T08:39:07.925273+00:00', elapsed_seconds=0.017858300008811057, thread=<Thread(bg-task_85fe2b7c, stopped daemon 16184)>).status
 +  and   <TaskStatus.DONE: 'done'> = TaskStatus.DONE
FAILED tests/test_sandbox.py::test_execute_simple_echo - assert False
 +  where False = SandboxResult(stdout='', stderr="Command not found: echo hello. Use 'bash -c' or 'cmd /c' explicitly if shell features are needed.", exit_code=127, was_timeout=False, was_killed=False, elapsed_ms=8.482399993226863, mode='subprocess', files_created=[], files_modified=[]).ok
FAILED tests/test_verifier.py::TestBrainVerifierIntegration::test_brain_detects_critical - AssertionError: Expected html or generic, got none
assert 'none' in ('html', 'generic')
FAILED tests/test_verifier.py::TestBrainVerifierIntegration::test_brain_passes_clean - AssertionError: Expected 0 criticals, got 999
assert 999 == 0
============================================================================ 4 failed, 503 passed, 1 skipped in 1444.36s (0:24:04) =============================================================================
PS &lt;project-dir&gt;>


4 failures واضحة جداً — ثلاثة منها مترابطة. إليك التشخيص الدقيق لكل واحدة:

---

## الفشل 1 & 2 — `echo hello` على Windows

```
Command not found: echo hello.
Use 'bash -c' or 'cmd /c' explicitly if shell features are needed.
```

**السبب:** `echo` على Windows ليست executable مستقلة — هي built-in داخل `cmd.exe`. بعد إصلاح ISS-002 وتغيير `_split_command` لتستخدم `shell=False`، أصبح `["echo", "hello"]` يفشل على Windows لأن Python لا تجد الملف.

**الحل في `core/sandbox.py`** — أضف Windows built-ins للـ `_split_command`:

```python
_WINDOWS_BUILTINS = {
    "echo", "dir", "cls", "del", "copy", "move",
    "type", "set", "cd", "md", "rd", "mkdir", "rmdir",
}

@staticmethod
def _split_command(command: str) -> tuple[list[str] | str, bool]:
    SHELL_CHARS = {"|", ">", "<", "&&", "||", ";", "$", "`",
                   "*", "?", "[", "]", "~", "!", "{", "}"}
    try:
        parts = shlex.split(command)
        # Windows shell built-ins require shell=True
        if os.name == "nt" and parts and parts[0].lower() in _WINDOWS_BUILTINS:
            return command, True
        for part in parts:
            for char in SHELL_CHARS:
                if char in part:
                    return command, True
        return parts, False
    except ValueError:
        return command, True
```

---

## الفشل 3 & 4 — `TestBrainVerifierIntegration`

```
Expected html or generic, got none
Expected 0 criticals, got 999
```

**السبب:** هذان الفشلان ناتجان عن إصلاح GAP #3 (ربط `CodeRunner` بالـ pipeline). الكود الجديد يحاول استخراج بلوكات Python بـ regex، لكن في هذين الاختبارين المدخلات لا تحتوي على ````python` blocks. النتيجة:

- الـ verifier type يُعاد كـ `"none"` بدل `"html"` أو `"generic"`
- الـ criticals تُعاد كـ `999` — وهو على الأرجح sentinel value في الكود الجديد يشير لـ "فشل التحقق من الكود"

**الحل في `core/uil/brain.py`** — أضف guard قبل تشغيل `CodeRunner`:

```python
# في الكود الجديد داخل brain.py بعد VERIFY step
if classification.task_type in (TaskType.CODE_WRITE, TaskType.CODE_MODIFY):
    import re
    code_blocks = re.findall(r'```python\n(.*?)```', raw_text, re.DOTALL)

    # Guard: لا تشغّل CodeRunner إذا لم يكن هناك Python code
    if code_blocks:
        from core.validation.runner import CodeRunner
        runner = CodeRunner(timeout_default=15)
        for code in code_blocks:
            run_result = runner.run_python(code)
            if not run_result.success:
                from core.uil.contract import Finding, VerificationSeverity
                verification_report.findings.append(Finding(
                    severity=VerificationSeverity.HIGH,
                    message=f"Runtime error: {run_result.stderr[:300]}",
                    category="runtime_validation"
                ))
    # لا sentinel value هنا — إذا لم يكن هناك كود فالتحقق نجح ضمنياً
```

---

## ملخص التعديلات المطلوبة

| الفشل | الملف | الإصلاح |
|-------|-------|---------|
| `test_execute_simple_echo` | `core/sandbox.py` | أضف `_WINDOWS_BUILTINS` check في `_split_command` |
| `test_background_run_and_status` | `core/sandbox.py` | نفس الإصلاح أعلاه (يُحل تلقائياً) |
| `test_brain_detects_critical` | `core/uil/brain.py` | أضف `if code_blocks:` guard قبل `CodeRunner` |
| `test_brain_passes_clean` | `core/uil/brain.py` | نفس الإصلاح أعلاه (يُحل تلقائياً) |

تعديلان فقط في ملفين — والـ 503 اختبار الناجحة لا تُمس.