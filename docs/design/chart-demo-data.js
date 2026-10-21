import { EMOTION_FIELDS } from '../../src/styles/echarts-theme.js';

// Fixed, synthetic teaching fixtures. No API or student records are read.
export const EMOTION_NAMES = Object.freeze({ joy:'喜悦', sadness:'悲伤', neutral:'平静', fear:'恐惧', anxiety:'焦虑', anger:'愤怒' });
export const CHANNEL_NAMES = Object.freeze(['在线交谈', '预约咨询', '同伴支持']);
export const WEEKDAYS = Object.freeze(['周一','周二','周三','周四','周五','周六','周日']);
export const TIME_SLOTS = Object.freeze(['09–12时','12–15时','15–18时','18–21时']);
const RESOURCE_NAMES = ['认识情绪','睡前放松','考试准备','人际沟通','呼吸练习','校园适应','自我关怀','求助指南'];
const sum = values => values.reduce((total, value) => total + value, 0);
const dateFor = index => new Date(Date.UTC(2026, 8, 22 + index));

export function getChartDemoData({ range = 14, sample = 'A' } = {}) {
  const count = [7,14,30].includes(Number(range)) ? Number(range) : 14;
  const offset = sample === 'B' ? 11 : 0;
  const daily = Array.from({length:30}, (_, index) => {
    const date = dateFor(index);
    const channels = [5 + (index * 3 + offset) % 8, 3 + (index + offset) % 5, 2 + (index * 2 + offset) % 4];
    const support = sum(channels);
    const slots = [2 + (index + offset) % 4, 1 + (index * 2 + offset) % 3, 3 + (index * 3 + offset) % 5, 1 + (index + offset) % 3];
    const planned = sum(slots);
    const completed = planned - (index + offset) % 4;
    return {
      date:date.toISOString().slice(0,10), label:`${date.getUTCMonth() + 1}/${date.getUTCDate()}`,
      weekday:(date.getUTCDay() + 6) % 7, support, channels, slots, planned, completed,
      emotions:EMOTION_FIELDS.map((_, field) => 1 + (index * (field + 2) + offset + field * 3) % (field === 2 ? 13 : 8)),
      risks:[10 + (index + offset) % 7, 2 + (index * 2 + offset) % 4, 1 + (index + offset) % 2],
      durations:Array.from({length:support}, (_, record) => 6 + (index * 13 + record * 7 + offset * 3) % 69),
      resources:RESOURCE_NAMES.map((name, resource) => {
        const views = 9 + resource * 7 + (index * (resource + 2) + resource * 11 + offset) % 47;
        return { name, views, saves:Math.floor(views * (12 + (resource * 7 + offset) % 26) / 100) };
      }),
    };
  }).slice(-count);
  const emotions = EMOTION_FIELDS.map((field, index) => ({field, name:EMOTION_NAMES[field], value:sum(daily.map(day => day.emotions[index]))}));
  const risks = ['low','mid','high'].map((field, index) => ({field, name:['低风险','中风险','高风险'][index], value:sum(daily.map(day => day.risks[index]))}));
  const appointments = WEEKDAYS.map((name, weekday) => ({name, planned:sum(daily.filter(day => day.weekday === weekday).map(day => day.planned)), completed:sum(daily.filter(day => day.weekday === weekday).map(day => day.completed))}));
  const channels = [['工作日', false],['周末', true]].map(([name, weekend]) => {
    const days = daily.filter(day => (day.weekday >= 5) === weekend);
    const values = CHANNEL_NAMES.map((_, index) => sum(days.map(day => day.channels[index])));
    const total = sum(values);
    // Integer tenths sum to exactly 100.0%; the last part takes rounding remainder.
    const tenths = values.slice(0, -1).map(value => Math.round(value / total * 1000));
    tenths.push(1000 - sum(tenths));
    return { name, total, counts:values, percentages:tenths.map(value => value / 10) };
  });
  const heatmap = WEEKDAYS.flatMap((name, weekday) => TIME_SLOTS.map((slot, time) => ({name, slot, weekday, time, value:sum(daily.filter(day => day.weekday === weekday).map(day => day.slots[time]))})));
  const durations = daily.flatMap(day => day.durations);
  const histogram = Array.from({length:8}, (_, index) => ({ min:index * 10, max:(index + 1) * 10, name:`${index * 10}–${index * 10 + 9}`, value:durations.filter(value => value >= index * 10 && value < (index + 1) * 10).length }));
  const resources = RESOURCE_NAMES.map((name, index) => ({name, views:sum(daily.map(day => day.resources[index].views)), saves:sum(daily.map(day => day.resources[index].saves))}));
  return { range:count, sample:sample === 'B' ? 'B':'A', period:`${daily[0].date} 至 ${daily.at(-1).date}`, daily, emotions, risks, appointments, channels, heatmap, durations, histogram, resources };
}
