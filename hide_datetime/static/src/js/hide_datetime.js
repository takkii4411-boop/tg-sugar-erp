/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DateTimeField } from "@web/views/fields/datetime/datetime_field";

patch(DateTimeField.prototype, {
    setup() {
        super.setup();
        
        const originalProps = this.props;
        this.props = new Proxy(originalProps, {
            get(target, prop) {
                if (prop === 'showTime') return false;
                return target[prop];
            }
        });
    },
});