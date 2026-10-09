# Accessibility

OVTK aims to make its local commands, documentation, and investigation outputs understandable and usable. Accessibility feedback is welcome through the **Help or usage question** or **Bug report** issue templates.

## Current interfaces

The project provides a command-line interface, a keyboard-driven console, Markdown documentation, structured CSV/JSON outputs, notebooks, figures, and PDF reports. It has no production graphical desktop interface at the current development checkpoint.

The console provides help and a plain stream mode when input or output is redirected. Use `console --no-style` to disable optional styling. Inquiry details support a vertical display, and exports provide structured alternatives to terminal tables.

## Known limitations

Screen-reader behavior across terminals has not been comprehensively verified. Width-dependent tables, figures, notebook output, and PDF layout may present barriers. Tagged PDF accessibility, color-vision coverage, and complete assistive-technology compatibility have not been established. No accessibility certification is claimed.

## Reporting a barrier

Describe the command, document, or output involved; your operating system and terminal; any assistive technology you choose to identify; and the behavior you need. A small synthetic example is helpful. Do not include personal or confidential data.

Improvements should preserve keyboard access, readable text, clear labels, and structured output alternatives. Accessibility fixes can be proposed through the normal contribution workflow.
