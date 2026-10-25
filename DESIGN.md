# CareRoute interface system

## Direction

CareRoute is a working clinic intake and review tool. The interface is designed for a laptop in a well-lit demonstration room: a light task surface, readable controls, quiet context, and a clear next action. A restrained aubergine accent and faint lilac neutrals distinguish the workspace without making model infrastructure its visual centerpiece.

## Color tokens

- Ink: `oklch(29% .025 305)`
- Secondary text: `oklch(52% .014 305)`
- Primary action and selection: `oklch(43% .085 315)`
- Primary hover: `oklch(36% .08 315)`
- Selection surface: `oklch(95% .018 310)`
- Canvas: `oklch(98% .004 310)`
- Content surface: `oklch(99.8% .001 310)`
- Navigation surface: `oklch(96% .008 310)`
- Dividers: `oklch(90% .009 310)`
- Input and segmented-control boundaries: `oklch(64% .018 310)`
- Emergency text: `oklch(46% .13 25)`
- Warning surface: `oklch(97% .023 75)`
- Connected state: `oklch(43% .07 155)`

Input and segmented-control borders use the dedicated control token to maintain at least 3:1 contrast against their adjacent surfaces. Keep decorative divider lines separate. Hovered fields and selected controls use the existing action or warning colors.

Status always includes text. Accent color marks actions and selected controls; it does not decorate inactive content. Alerts use a complete border and a meaningful icon, never a thick side stripe.

## Typography and spacing

Use one native family: Segoe UI Variable, Segoe UI, then platform system fonts. Desktop page headings are 28px, section headings 19px, input and primary form labels 14px. Supporting text is at least 12px. Original request text and AI excerpts remain 14px with comfortable line spacing. Do not add a display font or promotional hero treatment.

Spacing follows task hierarchy: 8–12px within related controls, 17–23px between field groups, 27–30px within intake sections, and 32px between the main task and context rail. Buttons and inputs share a 6px radius; the complete form sheet uses 12px. Avoid repeating individual bordered cards for every section.

## Layout and behavior

- A narrow desktop navigation rail anchors the workspace. On phones it becomes a compact header and three navigation tabs.
- Intake is one continuous sheet: description, immediate concerns, practical details. Emergency guidance stays visible independently of the form.
- A quiet context rail shows actual field completion, actual local model status, staff responsibility, and demonstration controls.
- At compact widths the same model status element moves before the form. It is never duplicated or replaced by a static readiness claim.
- A saved receipt replaces the editable form; “New request” starts another. AI assessment, staff review and booking remain separate visible states.
- Staff work uses an inbox and detail layout. Original text, AI excerpts, decisions and audit history remain inspectable.
- Retain keyboard focus, drafts, reduced-motion support, and existing error/fallback behavior through future refinements.
