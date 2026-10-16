/** @odoo-module **/
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { ListController } from '@web/views/list/list_controller';
import { listView } from '@web/views/list/list_view';

class MeetingListController extends ListController {
    setup() {
        super.setup();
        this.meetingOrm = useService('orm');
        this.meetingActions = useService('action');
    }
    async createRecord() {
        const action = await this.meetingOrm.call('community.meeting', 'action_create_guided', []);
        return this.meetingActions.doAction(action, { onClose: () => this.model.load() });
    }
}
registry.category('views').add('community_meeting_list', { ...listView, Controller: MeetingListController });
