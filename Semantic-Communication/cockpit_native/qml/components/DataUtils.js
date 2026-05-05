.pragma library

function normalize(value) {
    if (value === null || value === undefined)
        return value
    if (typeof value === "object" && typeof value.toVariant === "function")
        return value.toVariant()
    return value
}

function isArray(value) {
    value = normalize(value)
    if (Array.isArray && Array.isArray(value))
        return true
    if (value === null || value === undefined)
        return false
    if (typeof value === "string" || typeof value === "function")
        return false
    if (Object.prototype.toString.call(value) === "[object Array]")
        return true
    return typeof value === "object" && typeof value.length === "number" && value.length >= 0
}

function isObject(value) {
    value = normalize(value)
    return value !== null && typeof value === "object" && !isArray(value)
}

function objectOrEmpty(value) {
    var resolved = normalize(value)
    return isObject(resolved) ? resolved : ({})
}

function arrayOrEmpty(value) {
    var resolved = normalize(value)
    return isArray(resolved) ? resolved : []
}

function objectOrFallback(value, fallback) {
    var resolved = normalize(value)
    return isObject(resolved) ? resolved : objectOrEmpty(fallback)
}

function jsonObjectOrEmpty(value) {
    if (value === null || value === undefined)
        return ({})
    try {
        var parsed = JSON.parse(String(value))
        return objectOrEmpty(parsed)
    } catch (error) {
        return ({})
    }
}
