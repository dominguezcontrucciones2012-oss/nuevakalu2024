# Polish POS and Morosos Modules

This plan outlines the steps to make the POS and Morosos (Debt Control) interfaces flawless ("punta en blanco"). 

## User Review Required

> [!IMPORTANT]
> The current POS interface uses a custom premium dark/glassmorphic theme, while the Morosos screen still uses a lighter, standard Bootstrap card/table theme. 
> I will unify the visual style so that Morosos matches the modern, dark "glass" aesthetic of the POS. I will also clean up the payment drawer in both screens for maximum consistency.

## Proposed Changes

### UI & Styling Consistency
- **Morosos (`morosos.html`)**: 
  - Upgrade the main card to the `.card-pos` glassmorphic style.
  - Switch the table to a sleek dark/transparent table (`table-dark`, `bg-transparent`) instead of the default light bordered one.
  - Apply the premium glowing headers and text colors.
  - Align the "Abono" (Payment) drawer input styles to match exactly the POS payment drawer (dark inputs with border focus, animated badges).
- **POS (`pos.html`)**:
  - Minor alignment and padding tweaks to ensure pixel-perfect rendering.
  - Ensure all input fields in the payment drawer are properly aligned and readable.
  - Polish the summary footer.

### Logic & Robustness Check
- Review `routes/pos.py` and `routes/clientes.py` (Abonos) to ensure the dual-currency (USD/BS) calculations don't suffer from floating point errors by strictly using `Decimal` everywhere.
- Ensure the "Anti-Duplicado" lock works seamlessly in both.

## Open Questions

- Do you have any specific errors or visual glitches you've noticed in the POS or Morosos modules?
- Are you comfortable with translating the Morosos table completely to the dark/premium theme to match the POS?

## Verification Plan
1. **Visual Testing**: Verify both pages render correctly with the custom background and semi-transparent cards.
2. **Logic Validation**: Test calculations for both POS checkouts and Debt Abonos to guarantee correct remaining balance and change/vuelto without math precision errors.
