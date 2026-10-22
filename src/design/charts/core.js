import { use, registerTheme } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { AriaComponent } from 'echarts/components'
import { LabelLayout } from 'echarts/features'
import { installBusinessCharts } from '../chart-registry'

// Loaded through chart routes only. CSS palette initialization needs no chart runtime.
use([CanvasRenderer, AriaComponent, LabelLayout])
installBusinessCharts({ registerTheme })

export { init, getInstanceByDom, dispose, use } from 'echarts/core'
