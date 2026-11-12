import assert from 'node:assert/strict'
import { getChartDemoData } from '../docs/design/chart-demo-data.js'

// Semantic checks for the synthetic gallery, independent of ECharts rendering.
const report = {
  task: 'C3 chart data invariants',
  checkedAt: new Date().toISOString(),
  cases: [],
  errors: [],
}
const sum = (values) => values.reduce((total, value) => total + value, 0)
const count = (value) =>
  assert.ok(Number.isSafeInteger(value) && value >= 0, `Invalid count: ${value}`)
try {
  for (const sample of ['A', 'B'])
    for (const range of [7, 14, 30]) {
      const data = getChartDemoData({ sample, range })
      assert.deepEqual(data, getChartDemoData({ sample, range }), 'Fixtures must be deterministic')
      assert.equal(data.daily.length, range)
      assert.equal(new Set(data.daily.map((day) => day.date)).size, range)
      data.daily.forEach((day, index) => {
        if (index)
          assert.equal(Date.parse(day.date) - Date.parse(data.daily[index - 1].date), 86400000)
        ;[
          day.support,
          day.planned,
          day.completed,
          ...day.channels,
          ...day.slots,
          ...day.emotions,
          ...day.risks,
        ].forEach(count)
        assert.equal(day.support, sum(day.channels))
        assert.equal(day.planned, sum(day.slots))
        assert.ok(day.completed <= day.planned)
        assert.equal(day.durations.length, day.support)
        day.resources.forEach((row) => {
          count(row.views)
          count(row.saves)
          assert.ok(row.saves <= row.views)
        })
      })
      data.emotions.forEach((row, index) =>
        assert.equal(row.value, sum(data.daily.map((day) => day.emotions[index]))),
      )
      data.risks.forEach((row, index) =>
        assert.equal(row.value, sum(data.daily.map((day) => day.risks[index]))),
      )
      data.appointments.forEach((row, weekday) => {
        const days = data.daily.filter((day) => day.weekday === weekday)
        assert.equal(row.planned, sum(days.map((day) => day.planned)))
        assert.equal(row.completed, sum(days.map((day) => day.completed)))
      })
      assert.equal(
        sum(data.appointments.map((row) => row.planned)),
        sum(data.heatmap.map((row) => row.value)),
      )
      assert.equal(data.heatmap.length, 28)
      assert.equal(new Set(data.heatmap.map((row) => `${row.weekday}:${row.time}`)).size, 28)
      data.heatmap.forEach((row) =>
        assert.equal(
          row.value,
          sum(
            data.daily
              .filter((day) => day.weekday === row.weekday)
              .map((day) => day.slots[row.time]),
          ),
        ),
      )
      data.channels.forEach((row) => {
        assert.equal(row.counts.length, 3)
        assert.equal(row.total, sum(row.counts))
        row.counts.forEach(count)
        row.percentages.forEach((value) =>
          assert.ok(Number.isFinite(value) && value >= 0 && value <= 100),
        )
        assert.ok(Math.abs(sum(row.percentages) - 100) < 1e-9)
        row.percentages.forEach((value, index) =>
          assert.ok(Math.abs(value - (row.counts[index] / row.total) * 100) <= 0.11),
        )
      })
      assert.equal(
        sum(data.channels.map((row) => row.total)),
        sum(data.daily.map((day) => day.support)),
      )
      assert.equal(data.durations.length, sum(data.daily.map((day) => day.support)))
      assert.equal(sum(data.histogram.map((bin) => bin.value)), data.durations.length)
      data.histogram.forEach((bin, index) => {
        if (index)
          assert.equal(bin.min, data.histogram[index - 1].max, 'Bins must meet without overlap')
        assert.equal(
          bin.value,
          data.durations.filter((value) => value >= bin.min && value < bin.max).length,
        )
      })
      data.durations.forEach((value) =>
        assert.equal(data.histogram.filter((bin) => value >= bin.min && value < bin.max).length, 1),
      )
      data.resources.forEach((row, index) => {
        assert.equal(row.views, sum(data.daily.map((day) => day.resources[index].views)))
        assert.equal(row.saves, sum(data.daily.map((day) => day.resources[index].saves)))
        assert.ok(row.saves <= row.views)
      })
      const full = getChartDemoData({ sample, range: 30 })
      assert.deepEqual(data.daily, full.daily.slice(-range))
      report.cases.push({
        sample,
        range,
        supportRecords: data.durations.length,
        emotionRecords: sum(data.emotions.map((row) => row.value)),
        plannedAppointments: sum(data.appointments.map((row) => row.planned)),
        heatmapCells: data.heatmap.length,
        resourcePoints: data.resources.length,
        passed: true,
      })
    }
  assert.deepEqual(
    getChartDemoData({ sample: 'invalid', range: -1 }),
    getChartDemoData({ sample: 'A', range: 14 }),
  )
  assert.notDeepEqual(getChartDemoData({ sample: 'A' }), getChartDemoData({ sample: 'B' }))
  report.status = 'passed'
} catch (error) {
  report.status = 'failed'
  report.errors.push(String(error))
  process.exitCode = 1
}
console.log(JSON.stringify(report, null, 2))
