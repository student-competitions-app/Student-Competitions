// Submits a list's own form as soon as its value changes, so the cascading lists need no button.
document.addEventListener("change", (event) => {
  const list = event.target;
  if (list instanceof HTMLSelectElement && list.hasAttribute("data-auto-submit")) {
    list.form.requestSubmit();
  }
});
