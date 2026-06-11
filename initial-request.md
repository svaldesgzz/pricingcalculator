For the last year, Azure extended zones has struggled with providing cost estimations for customer workloads given it is not included in the Azure pricing calculator . I am providing 2 links to AWS and Azure pricing calculators as inspiration for the user interface that I want you to create . Azure Extended Zones has a smaller subset of services than regular Azure regions, so focus on only the ones that are provided in the excel files in this folder and create an Azure extended zones focused pricing calculator in which customers can estimate the cost for different workloads. 

For now, the excel files I'm providing are only for Luxembourg and Perth. The calculator should be able to select from a drop down either Perth or Luxembourg, and run the calculations for either depending on the selections and excel file pricing. For Los Angeles (the only other azure extended zones site available), just mention it will be available later in the pricing calculator. I want it to start with only these two sites.

The ideal scenario is for this calculator to be included in Azure Extended Zones' learn page. So, if this functionality is possible, make sure to format it in a way that I can later push to the azure-docs repo as a markdown file. That also means to keep a consistent format and a way to update and reference the excel files when prices change in the future.

Here's the list of services Azure Extended Zones provides:
https://learn.microsoft.com/en-us/azure/extended-zones/overview

Here's some inspiration for the UI:
https://calculator.aws/#/addService
https://azure.microsoft.com/en-us/pricing/calculator/
