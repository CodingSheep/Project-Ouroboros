// static/js/utils.js

export function formatTime(seconds) {
    if (!isFinite(seconds)) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

// Reorders an array based on a new order of elements
export function reorderArrayByDom(array, domElements, getElFn) {
    const newArray = [];
    domElements.forEach(d => {
        const item = array.find(a => getElFn(a) === d);
        if (item)
            newArray.push(item);
    });
    array.length = 0;
    newArray.forEach(n => array.push(n));
}
