document.addEventListener('DOMContentLoaded', function() {
    // Initialize all tag inputs
    const tagInputs = document.querySelectorAll('[data-role="tagsinput"]');
    
    tagInputs.forEach(input => {
        const options = {
            placeholder: input.getAttribute('placeholder') || 'Add tags...',
            duplicateTagClass: 'duplicate',
            onTagAdd: function(event, tag) {
                // Check for duplicates
                const tags = this.getTags();
                const duplicates = tags.filter(t => t === tag);
                if (duplicates.length > 1) {
                    const tagElement = this.getTagElement(tag);
                    tagElement.classList.add('duplicate');
                }
                // Update the input value
                input.value = tags.join(',');
            },
            onTagRemove: function(event, tag) {
                // Remove duplicate styling when tag is removed
                const tags = this.getTags();
                const duplicates = tags.filter(t => t === tag);
                if (duplicates.length <= 1) {
                    const tagElement = this.getTagElement(tag);
                    if (tagElement) {
                        tagElement.classList.remove('duplicate');
                    }
                }
                // Update the input value
                input.value = tags.join(',');
            },
            onBeforeTagAdd: function(event, tag) {
                // Split the tag by commas and add each part
                if (tag.includes(',')) {
                    const tags = tag.split(',').map(t => t.trim()).filter(t => t);
                    tags.forEach(t => this.add(t));
                    return false; // Prevent the original tag from being added
                }
                return true;
            }
        };

        // Initialize Taggle
        const taggle = new Taggle(input, options);

        // Add form submission handling
        const form = input.closest('form');
        if (form) {
            form.addEventListener('submit', function(e) {
                // Update the hidden input with the tags
                const hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = input.name;
                hiddenInput.value = taggle.getTags().join(',');
                form.appendChild(hiddenInput);
            });
        }
    });
}); 