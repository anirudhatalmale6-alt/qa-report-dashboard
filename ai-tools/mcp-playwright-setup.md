# MCP Playwright Setup Guide

## What is MCP Playwright?
MCP (Model Context Protocol) Playwright lets AI assistants (Claude, Copilot) directly control a browser. Instead of writing locators manually, AI sees the page and generates actions + locators for you.

## Prerequisites
- Node.js 18+ installed
- npm/npx available in PATH
- Playwright browsers installed (`npx playwright install`)

## Setup for Claude Code (CLI)

1. Open your project root folder (where conftest.py lives)
2. Create a file called `.mcp.json` with this content:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

3. Restart Claude Code in that folder
4. Claude Code will now have browser control tools available

## Setup for VS Code (Claude Extension or Copilot)

### Option 1: VS Code Settings (User-level)
Add to your VS Code `settings.json` (Ctrl+Shift+P > "Open User Settings JSON"):

```json
{
  "mcp": {
    "servers": {
      "playwright": {
        "command": "npx",
        "args": ["@playwright/mcp@latest"]
      }
    }
  }
}
```

### Option 2: Workspace-level (.vscode/mcp.json)
Create `.vscode/mcp.json` in your project root:

```json
{
  "servers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

## How to Use

### 1. Test Generation (Option A)
Ask Claude/AI to generate test code by describing what you want:

Example prompts:
- "Open https://uat25.example.com, login with user X, navigate to Work On Reports, and generate a @register_test method"
- "Look at the current page and generate Playwright locators for all form fields"
- "Record my interactions and create a test_ess_ui.py test method"

The AI will:
- Open the browser via MCP
- Navigate and interact with the app
- Identify elements and generate locators
- Write code matching your @register_test pattern

### 2. Locator Strategy (Fallback)
When locators break, ask:
- "This locator is broken: ESSPageLocators.WORK_ON_REPORTS_LINK - find the correct selector"
- "Take a screenshot of the current page and suggest better locators"
- "The table structure changed, find the new CSS selector for the unposted reports table"

### 3. Debugging Failed Tests
- "Navigate to this URL and check why the element is not found"
- "Take a screenshot after login to see what page we're on"

## Available MCP Playwright Tools

Once configured, the AI gets these browser tools:
- browser_navigate - Go to a URL
- browser_click - Click an element
- browser_type - Type text into a field
- browser_screenshot - Capture the current page
- browser_snapshot - Get page accessibility tree (for finding locators)
- browser_hover - Hover over an element
- browser_select - Select dropdown options
- browser_evaluate - Run JavaScript on the page
- browser_wait - Wait for elements
- browser_tab_* - Manage tabs
- browser_file_upload - Upload files
- browser_pdf_save - Save page as PDF

## Tips

1. Use `browser_snapshot` to get the accessibility tree - this gives the best locator suggestions
2. For your Struts-based app where IDs change, ask AI to find locators by text content or role
3. When generating tests, tell the AI about your @register_test decorator pattern
4. Always review generated locators before adding them to your locator files
