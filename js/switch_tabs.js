function scrollToTop() {
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function findButtonsByText(buttonText) {
  const buttons = document.getElementsByTagName("button");
  const matchingButtons = [];

  for (let i = 0; i < buttons.length; i++) {
    if (buttons[i].textContent.trim() === buttonText) {
      matchingButtons.push(buttons[i]);
    }
  }

  return matchingButtons;
}

function normalizeTabLabel(text) {
  return (text || "")
    .replace(/[\u{1F300}-\u{1FAFF}\u2600-\u27BF]/gu, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function gizmoGoToTab(targetLabel) {
  const target = normalizeTabLabel(targetLabel);
  if (!target) {
    return false;
  }

  const tabButtons = document.querySelectorAll(".tab-nav button");
  for (const button of tabButtons) {
    const current = normalizeTabLabel(button.textContent || "");
    if (current === target || current.includes(target) || target.includes(current)) {
      button.click();
      scrollToTop();
      return true;
    }
  }

  return false;
}

window.gizmoGoToTab = gizmoGoToTab;

function switch_to_chat() {
  gizmoGoToTab("Chat");
}

function switch_to_notebook() {
  gizmoGoToTab("Notebook");
  const rawButtons = findButtonsByText("Raw");
  if (rawButtons.length > 1) {
    rawButtons[1].click();
  }
  scrollToTop();
}

function switch_to_generation_parameters() {
  gizmoGoToTab("Parameters");
  const generationButtons = findButtonsByText("Generation");
  if (generationButtons.length > 0) {
    generationButtons[0].click();
  }
  scrollToTop();
}

function switch_to_character() {
  gizmoGoToTab("Character");
}

function switch_to_image_ai_generate() {
  gizmoGoToTab("Image");
  const container = document.querySelector("#image-ai-tab");
  if (!container) {
    return;
  }

  const buttons = container.getElementsByTagName("button");
  for (let i = 0; i < buttons.length; i++) {
    if (buttons[i].textContent.trim() === "Generate") {
      buttons[i].click();
      break;
    }
  }

  scrollToTop();
}
