import { use } from './core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, GraphicComponent, MarkPointComponent } from 'echarts/components'

use([LineChart, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent, GraphicComponent, MarkPointComponent])
export { init, getInstanceByDom, dispose } from './core'
