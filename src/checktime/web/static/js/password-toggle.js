// Auto-attach a "show / hide" toggle to every <input type="password"> on the
// page. Triggered on DOMContentLoaded — no template changes required.
//
// Use case: when a CheckJC login fails the operator wants to verify the
// stored password is what they think it is, without having to retype it.
// This is the simplest way to do that across all auth + profile + admin
// forms without touching half a dozen templates.
//
// Visual: wraps each password input in a Bootstrap input-group with a
// secondary-outline button to the right. The button shows bi-eye when the
// input is masked, bi-eye-slash when it's visible.

(function () {
    "use strict";

    function wrapWithToggle(input) {
        // Skip inputs that have already been wrapped (idempotent in case
        // a page injects more content later and we re-run).
        if (input.dataset.toggleAttached === "1") return;
        if (input.parentElement && input.parentElement.classList.contains("input-group")
            && input.parentElement.dataset.passwordToggleWrapper === "1") {
            return;
        }

        // Build the button. Plain <button type="button"> so it never
        // accidentally submits the form when clicked.
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-outline-secondary";
        btn.tabIndex = -1; // don't steal Tab from the form flow
        btn.setAttribute("aria-label", "Show password");
        var icon = document.createElement("i");
        icon.className = "bi bi-eye";
        btn.appendChild(icon);

        btn.addEventListener("click", function () {
            var isPassword = input.type === "password";
            input.type = isPassword ? "text" : "password";
            icon.className = isPassword ? "bi bi-eye-slash" : "bi bi-eye";
            btn.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
        });

        // Wrap input + button in an input-group. If the input is already
        // inside an input-group (rare in this app), append into that one
        // instead of creating a new wrapper.
        var existingGroup = input.closest(".input-group");
        if (existingGroup) {
            existingGroup.appendChild(btn);
        } else {
            var wrapper = document.createElement("div");
            wrapper.className = "input-group";
            wrapper.dataset.passwordToggleWrapper = "1";
            input.parentNode.insertBefore(wrapper, input);
            wrapper.appendChild(input);
            wrapper.appendChild(btn);
        }

        input.dataset.toggleAttached = "1";
    }

    function attachToAll() {
        var inputs = document.querySelectorAll('input[type="password"]');
        inputs.forEach(wrapWithToggle);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", attachToAll);
    } else {
        attachToAll();
    }
})();
