# CoCo Kiosk UI Design Sandbox

This folder contains a standalone, pure frontend implementation of the redesigned CoCo Kiosk interface.

## Purpose
- **Mock Design**: Test layout, typography, and touch interactions without running the Python backend.
- **Kiosk-First**: Large touch targets, high readability, and simplified interactions.

## How to Preview
Simply open `index.html` in any web browser.

## Design Decisions
- **Typography**: Base font size increased to `22px` (from 16px) for readability at arm's length.
- **Touch Targets**: Buttons are larger with generous padding.
- **Layout**: Fixed `100vh` layout to prevent scrolling the whole page; only the chat area scrolls.
- **Feedback**: Immediate visual feedback for "Searching..." state.
- **Contrast**: Using `#0056b3` (Dark Blue) for primary actions to pass WCAG AAA for large text.

## File Structure
- `index.html`: Structure.
- `styles.css`: Visuals and animations.
- `app.js`: Logic to simulate chat interactions with mock data.
