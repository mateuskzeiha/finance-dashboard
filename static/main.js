async function loadSummary() {
  try {
    const res = await fetch("/api/summary");
    const data = await res.json();

    const summary = data.summary || [];
    if (!summary.length) {
      console.log("Sem dados para resumo ainda.");
      return;
    }

    const labels = summary.map((row) => row.year_month);
    const incomes = summary.map((row) => row.income);
    const expenses = summary.map((row) => row.expense);
    const totals = summary.map((row) => row.total);
    const cumulative = summary.map((row) => row.cumulative_balance);

    // Atualiza cards
    const saldoAcumulado = cumulative[cumulative.length - 1];
    const ultimoMes = totals[totals.length - 1];
    const ultimos3 = totals.slice(-3);
    const media3 =
      ultimos3.reduce((acc, v) => acc + v, 0) / (ultimos3.length || 1);

    document.getElementById("saldo-acumulado").innerText =
      formatBRL(saldoAcumulado);
    document.getElementById("ultimo-mes").innerText = formatBRL(ultimoMes);
    document.getElementById("media-3m").innerText = formatBRL(media3);

    // Monta gráfico
    const ctx = document.getElementById("summaryChart").getContext("2d");

    new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Receitas",
            data: incomes,
            borderColor: "rgba(75, 192, 192, 1)",
            backgroundColor: "rgba(75, 192, 192, 0.2)",
            tension: 0.2,
          },
          {
            label: "Despesas",
            data: expenses,
            borderColor: "rgba(255, 99, 132, 1)",
            backgroundColor: "rgba(255, 99, 132, 0.2)",
            tension: 0.2,
          },
          {
            label: "Saldo do mês",
            data: totals,
            borderColor: "rgba(54, 162, 235, 1)",
            backgroundColor: "rgba(54, 162, 235, 0.2)",
            tension: 0.2,
          },
          {
            label: "Saldo acumulado",
            data: cumulative,
            borderColor: "rgba(153, 102, 255, 1)",
            backgroundColor: "rgba(153, 102, 255, 0.1)",
            tension: 0.2,
            yAxisID: "y1",
          },
        ],
      },
      options: {
        responsive: true,
        interaction: {
          mode: "index",
          intersect: false,
        },
        stacked: false,
        scales: {
          y: {
            type: "linear",
            position: "left",
          },
          y1: {
            type: "linear",
            position: "right",
            grid: {
              drawOnChartArea: false,
            },
          },
        },
      },
    });
  } catch (err) {
    console.error("Erro ao carregar resumo:", err);
  }
}

function formatBRL(value) {
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadSummary();
});
