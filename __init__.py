"""Hermes entry point; importing the plugin never captures or writes files."""


def register(ctx):
    from .orphic_tools import TOOL_DEFINITIONS
    from .commands import handle_command

    for name, schema, handler in TOOL_DEFINITIONS:
        ctx.register_tool(name=name, toolset="sightdiff", schema=schema, handler=handler)
    ctx.register_command("sightdiff", handler=handle_command,
                         description="Local visual regression: doctor, demo, help",
                         args_hint="doctor|demo|help")
