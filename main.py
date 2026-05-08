from runtime_utils import terminate_previous_arena_duel_instances
from ui.auto_update import run_startup_update_gate
from ui.launcher import run_main_mode_menu

if __name__ == "__main__":
    terminate_previous_arena_duel_instances()
    run_startup_update_gate()
    run_main_mode_menu()
