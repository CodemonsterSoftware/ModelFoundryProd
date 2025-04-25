document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing Taggle.js');
    
    // Initialize Taggle.js for all tags inputs
    const tagsContainers = document.querySelectorAll('.taggle-container');
    console.log('Found', tagsContainers.length, 'tag containers');
    
    // Store references to Taggle instances
    window.taggleInstances = [];
    
    tagsContainers.forEach(function(container, index) {
        console.log('Processing container', index);
        
        // Log container properties
        console.log('Container classes:', container.className);
        console.log('Container style:', container.getAttribute('style'));
        console.log('Container parent:', container.parentNode.className);
        
        // Get the hidden input
        const hiddenInput = container.querySelector('input[type="hidden"]');
        if (!hiddenInput) {
            console.log('No hidden input found, skipping');
            return;
        }
        
        // Clear any existing content in the container except the hidden input
        Array.from(container.children).forEach(child => {
            if (child !== hiddenInput) {
                console.log('Removing child:', child);
                child.remove();
            }
        });
        
        // Create a div for Taggle to use
        const taggleElement = document.createElement('div');
        taggleElement.className = 'tags-input';
        
        // Remove borders from container
        container.style.border = 'none';
        container.style.background = 'none';
        container.style.padding = '0';
        container.style.margin = '0';
        
        container.appendChild(taggleElement);
        
        // Get initial tags
        let initialTags = [];
        if (hiddenInput.value) {
            initialTags = hiddenInput.value.split(',')
                .map(tag => tag.trim())
                .filter(tag => tag);
            console.log('Initial tags:', initialTags);
        }
        
        // Initialize Taggle on the new element
        const taggle = new Taggle(taggleElement, {
            tags: initialTags,
            allowDuplicates: false,
            duplicateTagClass: 'duplicate',
            placeholder: 'Add tags...',
            preserveCase: false,
            containerClass: 'taggle_container',
            tagClass: 'taggle',
            closeClass: 'taggle_close',
            inputClass: 'taggle_input',
            submitKeys: [13, 188], // Enter and comma keys
            onBeforeTagAdd: function(event, tag) {
                // Remove comma if it was used to create the tag
                if (tag.endsWith(',')) {
                    tag = tag.slice(0, -1);
                }
                return tag.length > 0;
            },
            onTagAdd: function(event, tag) {
                // Update the hidden input with the current tags
                const tags = taggle.getTags().values;
                hiddenInput.value = tags.join(',');

                // Update close buttons with Font Awesome icons
                updateCloseButtons(taggleElement);
            },
            onBeforeTagRemove: function(event, tag) {
                return true;
            },
            onTagRemove: function(event, tag) {
                // Update the hidden input with the current tags
                const tags = taggle.getTags().values;
                hiddenInput.value = tags.join(',');
            }
        });

        // Handle input behavior
        const taggleInput = taggleElement.querySelector('.taggle_input');
        if (taggleInput) {
            // Set a non-conflicting name to prevent duplicate form submission
            taggleInput.setAttribute('name', '_taggle_input');
            
            // Handle keydown events
            taggleInput.addEventListener('keydown', function(e) {
                // Prevent form submission on enter
                if (e.key === 'Enter') {
                    e.preventDefault();
                }
                
                // Handle tab key
                if (e.key === 'Tab') {
                    const value = this.value.trim();
                    if (value) {
                        e.preventDefault();
                        taggle.add(value);
                        this.value = '';
                    }
                }
            });
        }

        // Initial update of close buttons
        updateCloseButtons(taggleElement);
        
        // Store reference to the Taggle instance
        window.taggleInstances.push(taggle);
    });

    // Function to update close buttons with Font Awesome icons
    function updateCloseButtons(container) {
        const closeButtons = container.querySelectorAll('.taggle_close');
        closeButtons.forEach(button => {
            if (!button.classList.contains('fa-initialized')) {
                button.innerHTML = '<i class="fas fa-times"></i>';
                button.classList.add('fa-initialized');
            }
        });
    }
}); 