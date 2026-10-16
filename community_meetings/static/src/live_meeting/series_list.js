/** @odoo-module **/
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { ListController } from '@web/views/list/list_controller';
import { listView } from '@web/views/list/list_view';

class MeetingSeriesListController extends ListController {
    setup() {
        super.setup();
        this.seriesOrm = useService('orm');
        this.seriesActions = useService('action');
    }
    async createRecord() {
        const action = await this.seriesOrm.call('community.meeting.series', 'action_create_series', []);
        return this.seriesActions.doAction(action, { onClose: () => this.model.load() });
    }
}
registry.category('views').add('community_meeting_series_list', { ...listView, Controller: MeetingSeriesListController });
