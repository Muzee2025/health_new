import { use } from './core'
import { LineChart, BarChart, PieChart, HeatmapChart, GraphChart, RadarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  VisualMapComponent,
  GraphicComponent,
} from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

// Print/export retains the SVG renderer; ordinary report charts retain Canvas.
use([
  LineChart,
  BarChart,
  PieChart,
  HeatmapChart,
  GraphChart,
  RadarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  VisualMapComponent,
  GraphicComponent,
  SVGRenderer,
])
export { init, getInstanceByDom, dispose } from './core'
