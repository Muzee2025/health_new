import { use } from './core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'

use([RadarChart, TooltipComponent, LegendComponent])
export { init, getInstanceByDom, dispose } from './core'
