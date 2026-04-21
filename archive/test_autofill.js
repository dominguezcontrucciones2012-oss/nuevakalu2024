const total_usd = 20.00;
const tasa_dia = 480;

function autoFillPago(inputId, values) {
    const p_usd = parseFloat(values.pago_usd) || 0;
    const p_bs_efec = parseFloat(values.pago_bs_efec) || 0;
    const p_pm = parseFloat(values.pago_pm) || 0;
    const p_deb = parseFloat(values.pago_debito) || 0;
    const p_bio = parseFloat(values.pago_bio) || 0;

    const total_pagado = p_usd + ((p_bs_efec + p_pm + p_deb + p_bio) / tasa_dia);
    const saldo_usd = total_usd - total_pagado;

    if (saldo_usd <= 0.001) return "YA PAGADO. NO HACE NADA"; 

    const esBs = ['pago_bs_efec', 'pago_pm', 'pago_debito', 'pago_bio'].includes(inputId);
    const valor = esBs ? (saldo_usd * tasa_dia) : saldo_usd;

    const valorEntero = Math.round(valor * 100);
    return (parseFloat(valorEntero / 100) || 0).toFixed(2);
}

console.log("Bs click WITH existing value:", autoFillPago('pago_pm', {pago_usd:'5', pago_bs_efec:'', pago_pm:'1000', pago_debito:'', pago_bio:''}));
console.log("Bs click with EXACT same value:", autoFillPago('pago_pm', {pago_usd:'', pago_bs_efec:'', pago_pm:'9600', pago_debito:'', pago_bio:''}));
