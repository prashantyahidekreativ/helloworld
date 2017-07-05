odoo.define('website.webcontroller_demo', function (require) {
"use strict";

var ajax = require('web.ajax');

$( document ).ready(function() {
	$('#cust_table').hide();

$('body').off('click','#contract-submit').on('click','#contract-submit', function(){
	var loc = "/customercontract"; 
	var serial_no = $('#cust-no').val();
	var contract_no = $('#contract_no').val();
	ajax.jsonRpc(loc,'call', {'params':{'serial_no':serial_no,'contract_no':contract_no}}).then(function(data){
		$('#cust_table').show();
		console.log(data['values']);
		
		var return_data = data;
        
		var tbody_content = "";
        debugger;
		if (return_data['values'].length != 0){
		$.each(return_data.values, function (index, item) {
		  if (item.draft=='draft'){
			  debugger;
			  $('#cust_table').hide();
		   	  $('#error').show()
		   	  $('#error').text('Contract is not Activated Yet');
		  }
		  else{	  
			tbody_content += 
		    "<tr>" +
		      "<td>" + item.name + "</td>" +
		      "<td>" + item.partner_name + "</td>" +
		      "<td>" + item.date_active + "</td>" +
		      "<td>" + item.val_date + "</td>" +
		      "</tr>";
			$('#error').hide();
			$('.table').find('tbody').html(tbody_content);
		  }
		});
		/*$('#error').hide();
		$('.table').find('tbody').html(tbody_content);
        */
       }
     else{
   		$('#cust_table').hide();
   		$('#error').show()
   		$('#error').text('Please Give valid serial no or contract no');
   	  } 
        
		});
	   
	
});
	
});
});