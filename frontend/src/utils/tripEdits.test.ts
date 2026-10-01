import { describe, expect, it } from 'vitest'

import type { Attraction, TripPlan } from '@/types'
import { buildEditOperations, type EditableAttraction } from './tripEdits'


const attraction = (id: string, duration = 120): Attraction => ({
  poi_id: id,
  name: id,
  address: `${id}地址`,
  location: { longitude: 116, latitude: 39 },
  visit_duration: duration,
  description: id,
  ticket_price: 10
})

const plan = (items: Attraction[]): TripPlan => ({
  city: '北京',
  start_date: '2026-10-01',
  end_date: '2026-10-01',
  days: [{
    date: '2026-10-01',
    day_index: 0,
    description: '',
    transportation: '公共交通',
    accommodation: '经济型酒店',
    attractions: items,
    meals: [],
    travel_legs: []
  }],
  weather_info: [],
  overall_suggestions: '',
  status: 'success',
  warnings: []
})

describe('buildEditOperations', () => {
  it('生成删除、调序和停留时间操作', () => {
    const before = plan([attraction('A'), attraction('B'), attraction('C')])
    const after = plan([attraction('C', 180), attraction('A')])

    expect(buildEditOperations(before, after)).toEqual([
      { type: 'delete_attraction', day_index: 0, attraction_index: 1 },
      { type: 'move_attraction', day_index: 0, attraction_index: 1, target_index: 0 },
      { type: 'update_visit_duration', day_index: 0, attraction_index: 0, visit_duration: 180 }
    ])
  })

  it('替换后仍以原景点身份计算位置', () => {
    const before = plan([attraction('A'), attraction('B')])
    const replacement = {
      ...attraction('X'),
      replacement_poi_id: 'X',
      replacement_source_id: 'A'
    } as EditableAttraction
    const after = plan([replacement, attraction('B')])

    expect(buildEditOperations(before, after)).toEqual([
      {
        type: 'replace_attraction',
        day_index: 0,
        attraction_index: 0,
        replacement_poi_id: 'X'
      }
    ])
  })
})
