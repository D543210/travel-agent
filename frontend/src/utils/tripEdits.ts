import type { Attraction, TripEditOperation, TripPlan } from '@/types'

export type EditableAttraction = Attraction & {
  replacement_poi_id?: string
  replacement_source_id?: string
}

export function buildEditOperations(before: TripPlan, after: TripPlan): TripEditOperation[] {
  const operations: TripEditOperation[] = []

  after.days.forEach((day, dayIndex) => {
    const original = before.days[dayIndex].attractions
    const workingIds = original.map(item => item.poi_id || item.name)
    const finalIds = day.attractions.map(item => {
      const editable = item as EditableAttraction
      return editable.replacement_source_id || item.poi_id || item.name
    })

    for (let index = workingIds.length - 1; index >= 0; index--) {
      if (!finalIds.includes(workingIds[index])) {
        operations.push({ type: 'delete_attraction', day_index: dayIndex, attraction_index: index })
        workingIds.splice(index, 1)
      }
    }

    finalIds.forEach((poiId, targetIndex) => {
      const currentIndex = workingIds.indexOf(poiId)
      if (currentIndex !== targetIndex) {
        operations.push({
          type: 'move_attraction',
          day_index: dayIndex,
          attraction_index: currentIndex,
          target_index: targetIndex
        })
        const [moved] = workingIds.splice(currentIndex, 1)
        workingIds.splice(targetIndex, 0, moved)
      }
    })

    day.attractions.forEach((attraction, index) => {
      const editable = attraction as EditableAttraction
      if (editable.replacement_poi_id) {
        operations.push({
          type: 'replace_attraction',
          day_index: dayIndex,
          attraction_index: index,
          replacement_poi_id: editable.replacement_poi_id
        })
      }
    })

    day.attractions.forEach((attraction, index) => {
      const old = original.find(item => (item.poi_id || item.name) === finalIds[index])
      if (old && old.visit_duration !== attraction.visit_duration) {
        operations.push({
          type: 'update_visit_duration',
          day_index: dayIndex,
          attraction_index: index,
          visit_duration: attraction.visit_duration
        })
      }
    })
  })

  return operations
}
