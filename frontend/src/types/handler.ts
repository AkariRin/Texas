/** Handler/Controller type definitions. */

export interface HandlerMethodInfo {
  method: string
  mappingType: string
  priority: number
}

export interface ControllerInfo {
  name: string
  description: string
  version: string
  class: string
  defaultPriority: number
  handlerCount: number
  methods: HandlerMethodInfo[]
}

export interface InterceptorInfo {
  name: string
  enabled: boolean
}

