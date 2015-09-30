var URL_STATUS = '/deploy/repo/repo_name/status'
var URL_CANCEL = '/deploy/repo/repo_name/cancel';
var URL_ENABLE_AUTO = '/deploy/repo/repo_name/enable_auto';
var URL_DISENABLE_AUTO = '/deploy/repo/repo_name/disable_auto';
var URL_ROLLBACK = '/deploy/repo/repo_name/rollback/commit/tag';
var URL_LOGOUT = '/deploy/logout';

// 更新状态数据
function reloadStatusData(){
   var url = URL_STATUS.replace('repo_name', $( '#label_repo' ).text());
   $.ajax({
         url: url,
         type: 'GET',
         dataType: 'json',
         success: function(data) {
            // 更新status 1:running 2:rollback 3:idle
            var status = data.status;
            if (status == 1) {
               $( '#label_repo_status' ).removeClass('label-primary').removeClass('label-danger').addClass('label-success');
               $( '#label_repo_status' ).text('部署中');
            }
            else if (status == 2) {
               $( '#label_repo_status' ).removeClass('label-primary').removeClass('label-success').addClass('label-danger');
               $( '#label_repo_status' ).text('回滚中');
            }
            else if (status == 3) {
               $( '#label_repo_status' ).removeClass('label-danger').removeClass('label-success').addClass('label-primary');
               $( '#label_repo_status' ).text('空闲');
            }

            // 更新task_running
            if (data.task_running!==''){
               if (status == 1) {
                  $( '#label_task_running' ).text('正在部署' + data.task_running );
               }
               else if (status == 2) {
                  $( '#label_task_running' ).text('正在撤销部署' + data.task_running + '，并回滚' );
               }
            }
            else {
               $( '#label_task_running' ).text('无');
            }

            // 更新stage_info
            $( '#label_status_info' ).text(data.stage);

            // 更新host_status 1:normal 2:deploying 3:success 4:fault
            for (hostname in data.hosts_status){
               var host_status = data.hosts_status[hostname];
               if (host_status == 1) {
                  $( 'span[hostname='+ hostname +']' ).removeClass('label-info').removeClass('label-danger').removeClass('label-success').addClass('label-primary');
                  $( 'span[hostname='+ hostname +']' ).text('正常');
               }
               else if (host_status == 2) {
                  $( 'span[hostname='+ hostname +']' ).removeClass('label-primary').removeClass('label-danger').removeClass('label-success').addClass('label-info');
                  $( 'span[hostname='+ hostname +']' ).text('部署中');
               }
               else if (host_status == 3) {
                  $( 'span[hostname='+ hostname +']' ).removeClass('label-info').removeClass('label-danger').removeClass('label-primary').addClass('label-success');
                  $( 'span[hostname='+ hostname +']' ).text('部署成功');
               }
               else if (host_status == 4) {
                  $( 'span[hostname='+ hostname +']' ).removeClass('label-info').removeClass('label-success').removeClass('label-primary').addClass('label-danger');
                  $( 'span[hostname='+ hostname +']' ).text('部署失败');
               }
            };

            // 更新deploy status可见性
            set_deploy_status_display();

            // 如果last_commit发生变动，刷新本页面，该操作要在更新last_commit之前
            if ($( '#label_commit_id_hidden' ).text() !== data.last_commit) {
               location.reload(true);
            }

            // 如果task_waiting发生变动，刷新本页面
            if ($( '#tags_str_hidden' ) && $( '#tags_str_hidden' ).text() !== data.task_waiting.join(',')){
               location.reload(true);
            }

            // 更新last_commit
            $( '#label_commit_id_hidden' ).text(data.last_commit);
            if (data.last_commit_tag!==''){
               $( '#label_commit_id' ).text(data.last_commit + ' / ' + data.last_commit_tag);
               $( '#label_tag_hidden' ).text(data.last_commit_tag);
            }
            else {
               $( '#label_commit_id' ).text(data.last_commit);
               $( '#label_tag_hidden' ).text('');
            }

            set_tag_indicator();

            // 更新cancel_flag
            if (data.cancel_flag == false && $( '#btn_rollback_immediately' ).attr('disabled') == 'disabled' && status == 3)  {
               $( '#btn_rollback_immediately' ).removeAttr('disabled')
            }
            else if (status == 2){
               $( '#btn_rollback_immediately' ).attr('disabled','disabled')
            }

            // 更新auto_deploy按钮
            if (data.auto_deploy_enable == true){
               set_auto_deploy_enable();
            }
            else if (data.auto_deploy_enable == false){
               set_auto_deploy_disable();
            }

            // 更新进程条
            $( '#process-bar' ).css('width',data.process_percent + '%');
            $( '#process-bar' ).text(data.process_percent + '%');
         },
         complete: function() {
            setTimeout(reloadStatusData,3000);
         }
   });
};

// 立即回滚按钮
$( '#btn_rollback_immediately' ).click(function(){
   if (confirm('立即停止本次部署，并且回滚吗？')){
      var url = URL_CANCEL.replace('repo_name', $( '#label_repo' ).text());
//      alert(url);
      $.ajax({
         url: url,
         type: 'PUT',
         success: function() {
            alert('命令发送成功');
            $( '#btn_rollback_immediately' ).attr('disabled','disabled');
         },
         error: function() {
            alert('命令发送失败');
         }
      });
   };
})

// 是否启动自动部署
$( '#btn_auto_deploy_enable' ).click(function(){
   if (confirm('确认启动自动部署吗')){
      var url = URL_ENABLE_AUTO.replace('repo_name', $( '#label_repo' ).text());
//      alert(url);
      $.ajax({
         url: url,
         type: 'PUT',
         success: function() {
            alert('命令发送成功');
            set_auto_deploy_enable();
         },
         error: function() {
            alert('命令发送失败');
         }
      })
   }
})

$( '#btn_auto_deploy_disable' ).click(function(){
   if (confirm('确认关闭自动部署吗')){
      var url = URL_DISENABLE_AUTO.replace('repo_name', $( '#label_repo' ).text());
//      alert(url);
      $.ajax({
         url: url,
         type: 'PUT',
         success: function() {
            alert('命令发送成功');
            set_auto_deploy_disable();
         },
         error: function() {
            alert('命令发送失败');
         }
      })
   }
})

// 回滚到某个标签
$( '#btn_rollback_tag' ).click(function(){
   var tag_name = $( 'input[type=radio]:checked' ).attr('tag-name');
   // 没有选择标签
   if ($( 'input[type=radio]:checked' ).length<1) {
      alert('请选择回滚的目标标签！');
   }
   // 当前不为空闲
   else if (!$( '#label_repo_status' ).hasClass('label-primary')){
      alert('回滚需要在空闲状态下进行！');
   }
   else if ($( '#label_tag_hidden' ).text() == tag_name ){
      alert('当前仓库正处于该标签下，不需要回滚！');
   }
   else if ($( '#btn_auto_deploy_disable' ).hasClass('active')){
      alert('当前仓库自动部署已关闭，请启动后重试！');
   }
   else {
      if (confirm('确认要回滚到标签' + tag_name + '吗？')){
         var url = URL_ROLLBACK.replace('repo_name', $( '#label_repo' ).text())
                               .replace('commit', $( 'input[type=radio]:checked' ).attr('commit-id'))
                               .replace('tag', tag_name);
//         alert(url);
         $.ajax({
            url: url,
            type: 'PUT',
            success: function() {
               alert('命令发送成功');
               set_auto_deploy_disable();
            },
            error: function() {
               alert('命令发送失败');
            }
         })
      }
   }
})

function set_auto_deploy_enable(){
   $( '#btn_auto_deploy_enable' ).attr('disabled','disabled');
   $( '#btn_auto_deploy_enable' ).addClass('active');
   $( '#btn_auto_deploy_disable' ).removeAttr('disabled');
   $( '#btn_auto_deploy_disable' ).removeClass('active');
}

function set_auto_deploy_disable(){
   $( '#btn_auto_deploy_disable' ).attr('disabled','disabled');
   $( '#btn_auto_deploy_disable' ).addClass('active');
   $( '#btn_auto_deploy_enable' ).removeAttr('disabled');
   $( '#btn_auto_deploy_enable' ).removeClass('active');
}

function set_deploy_status_display(){
   // 当前不为空闲
   if (!$( '#label_repo_status' ).hasClass('label-primary')){
      $( '#div_deploy_status' ).removeClass('hidden');
   }
   else{
      $( '#div_deploy_status' ).addClass('hidden');
   }
}

function set_tag_indicator(){
   $( '.tag-indicator' ).addClass('hidden');
   var tag_now = $( '#label_tag_hidden' ).text();
   $( '.tag-indicator[tag-name="' + tag_now + '"]' ).removeClass('hidden');
}

$( document ).ready(function() {
   // Handler for .ready() called.
   setTimeout(reloadStatusData,3000);
   $( '[data-toggle="popover"]' ).popover();
   set_deploy_status_display();
   set_tag_indicator();
});