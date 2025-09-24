let chart;
let updateInterval;
let lastUpdateTime = 0;
let chartData;

function generateLegendLabels(chart) {
    const originalLabels = Chart.defaults.plugins.legend.labels.generateLabels(chart);
    const maxSpeedLabel = {
        text: `Vel Máx: ${chartData.max_speed}Km/h`,
        fillStyle: 'rgba(0,0,0,0)',
        strokeStyle: 'rgba(0,0,0,0)',
    };
    const maxRpmLabel = {
        text: `RPM Máx: ${chartData.max_rpm}`,
        fillStyle: 'rgba(0,0,0,0)',
        strokeStyle: 'rgba(0,0,0,0)',
    };
    return [...originalLabels, maxSpeedLabel, maxRpmLabel];
}

function createChart(data) {
    chartData = data;
    const ctx = document.getElementById('vehicleDataChart').getContext('2d');
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [
                {
                    label: 'Odômetro (Km)',
                    data: data.data.map(item => ({ 
                        x: moment(item.date_time).subtract(3, 'hours'),
                        y: item.odometer 
                    })).filter(point => point.y !== null),
                    borderColor: 'rgb(75, 192, 192)',
                    yAxisID: 'y',
                },
                {
                    label: 'Consumo Total (Litros)',
                    data: data.data.map(item => ({ 
                        x: moment(item.date_time).subtract(3, 'hours'),
                        y: item.fuel_consumption 
                    })).filter(point => point.y !== null),
                    borderColor: 'rgb(255, 99, 132)',
                    yAxisID: 'y1',
                },
                {
                    label: 'Contador RPM faixa verde (seg)',
                    data: data.data.map(item => ({ 
                        x: moment(item.date_time).subtract(3, 'hours'),
                        y: item.rpm_eco_time 
                    })).filter(point => point.y !== null),
                    borderColor: 'rgb(54, 162, 235)',
                    yAxisID: 'y2',
                },
                {
                    label: 'Eventos',
                    data: data.data.filter(item => item.event).map(item => ({
                        x: moment(item.date_time).subtract(3, 'hours'),
                        y: null,
                        event: item.event
                    })),
                    showLine: false,
                    pointStyle: 'line',
                    pointRadius: 0,
                    borderColor: 'rgba(0,0,0,0)',
                }
            ]
        },
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            stacked: false,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute',
                        displayFormats: {
                            minute: 'DD/MM/YYYY HH:mm'
                        },
                    },
                    ticks: {
                        source: 'auto',
                        maxTicksLimit: 35,
                        maxRotation: 45,
                        minRotation: 45,
                        autoSkip: true,
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Odômetro (Km)'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Consumo Total (Litros)'
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                },
                y2: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Contador RPM faixa verde (seg)'
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                }
            },
            plugins: {
                legend: {
                    labels: {
                        generateLabels: generateLegendLabels
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            if (context.dataset.label === 'Eventos') {
                                return context.raw.event;
                            }
                            let label = context.dataset.label || '';
                            return label + ': ' + context.parsed.y;
                        }
                    }
                }
            }
        },
        plugins: [{
            afterDraw: drawAlarmLines
        }]
    });
    chart.config.specificAlarms = data.specific_alarms;
    chart.update();
}

function drawAlarmLines(chart, args, options) {
    const specificAlarms = chart.config.specificAlarms || [];
    const ctx = chart.ctx;
    const xAxis = chart.scales.x;
    const yAxis = chart.scales.y;

    const alarmColors = {
        '53': 'green',
        '58': 'red',
        '104': 'blue',
        '112': 'orange',
        '101': 'purple',
        '109': 'brown',
        '108': 'darkred'
    };

    specificAlarms.forEach(alarm => {
        const x = xAxis.getPixelForValue(moment(alarm.date_time).subtract(3, 'hours'));
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(x, yAxis.top);
        ctx.lineTo(x, yAxis.bottom);
        ctx.lineWidth = 2;
        ctx.strokeStyle = alarmColors[alarm.code] || 'gray';
        ctx.stroke();
        ctx.restore();

        // Add vertically oriented label
        ctx.save();
        ctx.fillStyle = alarmColors[alarm.code] || 'gray';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.font = '12px Arial';

        ctx.translate(x + 7, yAxis.top + 60);  // Move to position and adjust offset
        ctx.rotate(-Math.PI / 2);  // Rotate 90 degrees counter-clockwise
        ctx.fillText(alarm.label, 0, 0);
        ctx.restore();
    });
}

function fetchDataAndUpdateChart() {
    const terminalId = document.getElementById('terminalSelect').value;
    const startTime = document.getElementById('startTime').value;
    const endTime = document.getElementById('endTime').value;

    if (!terminalId || !startTime) {
        alert('Por favor, selecione um Terminal e insira a Hora Inicial');
        return;
    }

    document.getElementById('loadingMessage').style.display = 'block';

    let url = `/get_data?terminal_id=${terminalId}&start_time=${startTime}`;
    if (endTime) {
        url += `&end_time=${endTime}`;
    }

    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('A resposta da rede não foi bem-sucedida');
            }
            return response.json();
        })
        .then(data => {
            document.getElementById('loadingMessage').style.display = 'none';
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Sort the data by GPS timestamp
            data.data.sort((a, b) => moment(a.date_time).valueOf() - moment(b.date_time).valueOf());
            
            chartData = data;  // Update the global chartData
            if (chart) {
                updateChartData(data);
            } else {
                createChart(data);
            }
            lastUpdateTime = Date.now();
        })
        .catch(error => {
            console.error('Erro:', error);
            document.getElementById('loadingMessage').textContent = 'Erro ao carregar dados. Por favor, verifique o console para detalhes.';
        });
}

function updateChartData(data) {
    chart.data.datasets[0].data = data.data.map(item => ({ 
        x: moment(item.date_time).subtract(3, 'hours'),
        y: item.odometer 
    })).filter(point => point.y !== null);
    chart.data.datasets[1].data = data.data.map(item => ({ 
        x: moment(item.date_time).subtract(3, 'hours'),
        y: item.fuel_consumption 
    })).filter(point => point.y !== null);
    chart.data.datasets[2].data = data.data.map(item => ({ 
        x: moment(item.date_time).subtract(3, 'hours'),
        y: item.rpm_eco_time 
    })).filter(point => point.y !== null);
    chart.data.datasets[3].data = data.data.filter(item => item.event).map(item => ({
        x: moment(item.date_time).subtract(3, 'hours'),
        y: null,
        event: item.event
    }));
    chart.config.specificAlarms = data.specific_alarms;
    chart.options.plugins.legend.labels.generateLabels = generateLegendLabels;
    chart.update();
}

function updateChart() {
    const currentTime = Date.now();
    if (currentTime - lastUpdateTime < 60000) {
        // If less than 60 seconds have passed, wait for the next cycle
        return;
    }
    fetchDataAndUpdateChart();
}

function startUpdateCycle() {
    fetchDataAndUpdateChart();
    clearInterval(updateInterval);
    updateInterval = setInterval(updateChart, 120000); // Check every 60 seconds
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Select2 for terminal selection
    $('#terminalSelect').select2({
        placeholder: 'Buscar terminal por placa ou ID',
        allowClear: true,
        width: '300px',
        language: {
            noResults: function() {
                return "Nenhum terminal encontrado";
            }
        },
        matcher: function(params, data) {
            // If there are no search terms, return all of the data
            if ($.trim(params.term) === '') {
                return data;
            }

            // `params.term` is the search term
            // `data.text` is the terminal text (plate + ID)
            if (data.text.toLowerCase().indexOf(params.term.toLowerCase()) > -1) {
                return data;
            }

            // Return `null` if the term should not be displayed
            return null;
        }
    });

    document.getElementById('buscarButton').addEventListener('click', function(event) {
        event.preventDefault();
        startUpdateCycle();
    });
});