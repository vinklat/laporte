/* global 
    $
*/
/* jshint 
    unused:false
*/

const htmlEncode = (str) => {
    return str.replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/'/g, '&#39;')
        .replace(/"/g, '&#34;');
};

const isTruncated = (id) => {
    const elem = $('#eval-truncate');
    return elem.innerHeight() > elem.parent().innerHeight();
};

const checkTruncated = (id) => {
    const elem = $(id);
    const parent = $(elem).parent();
    parent.addClass('truncate-overflow');
    if (elem.innerHeight() > parent.innerHeight()) {
        parent.addClass('long');
    } else {
        parent.removeClass('truncate-overflow long');
    }
};

const logTrClass = (level) => {
    const tableClass = {
        light: 'table-light',
        info: 'table-info',
        warning: 'table-warning',
        danger: 'table-danger'
    };

    const levels = {
        'DEBUG': tableClass.light,
        'WARNING': tableClass.warning,
        'CRITICAL': tableClass.danger,
        'ERROR': tableClass.danger,
        'default': tableClass.info
    };

    return levels[level] || levels.default;
};

const is_same_day = (date1, date2) => {
    return (
        date1.getUTCFullYear() === date2.getUTCFullYear() &&
        date1.getMonth() === date2.getMonth() &&
        date1.getDate() === date2.getDate()
    );
};

const fmtMSS = (s) => {
    return (s - (s %= 60)) / 60 + (9 < s ? ':' : ':0') + s;
};

const locale = navigator.language;

const scrollToElement = (id, speed = 1000) => {
    $("html, body").animate({ scrollTop: $(id).offset().top }, speed);
};

const scrollToBottomAnimate = () => {
    scrollToElement('#log-end', 50);
};

const scrollToBottomInstant = () => {
    scrollToElement('#log-end', 1);
};

const checkboxChecked = (id) => {
    return ($(id).is(":checked"));
};

const followLogs = () => {
    return checkboxChecked('#followLogs');
};