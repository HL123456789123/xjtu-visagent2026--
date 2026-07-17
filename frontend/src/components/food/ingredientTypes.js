/**
 * @typedef {Object} BoundingBox
 * @property {number} x1
 * @property {number} y1
 * @property {number} x2
 * @property {number} y2
 */

/**
 * V1.1 API candidate returned by food recognition.
 *
 * @typedef {Object} IngredientCandidate
 * @property {string} candidate_id
 * @property {number} image_index
 * @property {string} class_name
 * @property {string} display_name
 * @property {number} confidence
 * @property {BoundingBox|null} bbox
 * @property {'model'|'manual'} source
 */

/**
 * V1 ingredient submitted after user confirmation.
 *
 * @typedef {Object} ConfirmedIngredient
 * @property {string} name
 * @property {string|null} class_name
 * @property {number} quantity
 * @property {string} unit
 * @property {'model'|'manual'} source
 */

export {}
